//! Deterministic feedback-weight adaptation, ported from `agentrouter/learning.py`.
//!
//! Every route recomputes the adjustment from stored ratings. There is no
//! learned state to drift: deleting feedback or disabling learning restores
//! the configured base weights.

use agentrouter_routing::{round_half_even, Weights};
use rusqlite::{params, Connection};

pub const MIN_FEEDBACK: i64 = 3;
pub const STEP: f64 = 0.01;
pub const MAX_SHIFT: f64 = 0.10;
pub const MIN_W_COST: f64 = 0.05;
pub const NEGATIVE_AT_OR_BELOW: i64 = 2;

/// Return adapted routing weights and an explanation, matching Python's
/// `learning.learned_weights` contract.
pub fn learned_weights(
    conn: &Connection,
    base: &Weights,
) -> rusqlite::Result<(Weights, Option<String>)> {
    let (total, negative): (i64, i64) = conn.query_row(
        "SELECT COUNT(*), COALESCE(SUM(rating <= ?1), 0) FROM feedback WHERE rating IS NOT NULL",
        params![NEGATIVE_AT_OR_BELOW],
        |row| Ok((row.get(0)?, row.get(1)?)),
    )?;
    if total < MIN_FEEDBACK || negative == 0 {
        return Ok((*base, None));
    }

    let shift = (STEP * negative as f64)
        .min(MAX_SHIFT)
        .min(base.w_cost - MIN_W_COST);
    if shift <= 0.0 {
        return Ok((*base, None));
    }

    let weights = Weights {
        w_cap: round_half_even(base.w_cap + shift, 4),
        w_cost: round_half_even(base.w_cost - shift, 4),
        ..*base
    };
    let note = format!(
        "learned from {total} rating(s), {negative} negative -> w_cap +{shift:.2}, w_cost -{shift:.2} (delete feedback or set learning: false to revert)"
    );
    Ok((weights, Some(note)))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn connection(ratings: &[Option<i64>]) -> Connection {
        let conn = Connection::open_in_memory().unwrap();
        conn.execute_batch(
            "CREATE TABLE feedback (id INTEGER PRIMARY KEY, rating INTEGER);
             CREATE TABLE decisions (id INTEGER PRIMARY KEY);",
        )
        .unwrap();
        for rating in ratings {
            conn.execute("INSERT INTO feedback (rating) VALUES (?1)", [rating])
                .unwrap();
        }
        conn
    }

    fn assert_same_weights(actual: Weights, expected: Weights) {
        assert_eq!(actual.w_cap, expected.w_cap);
        assert_eq!(actual.w_cost, expected.w_cost);
        assert_eq!(actual.w_lat, expected.w_lat);
        assert_eq!(actual.w_ctx, expected.w_ctx);
    }

    #[test]
    fn minimum_sample_and_positive_feedback_do_not_adapt() {
        let base = Weights::default();
        let conn = connection(&[Some(1), Some(2)]);
        let (weights, note) = learned_weights(&conn, &base).unwrap();
        assert_same_weights(weights, base);
        assert!(note.is_none());

        let conn = connection(&[Some(3), Some(4), Some(5)]);
        let (weights, note) = learned_weights(&conn, &base).unwrap();
        assert_same_weights(weights, base);
        assert!(note.is_none());
    }

    #[test]
    fn negative_feedback_shifts_and_caps_weights() {
        let base = Weights::default();
        let conn = connection(&[Some(1), Some(2), Some(5)]);
        let (weights, note) = learned_weights(&conn, &base).unwrap();
        assert_eq!(weights.w_cap, 0.47);
        assert_eq!(weights.w_cost, 0.23);
        assert!(note.unwrap().contains("2 negative"));

        let conn = connection(&[Some(1); 50]);
        let (weights, _) = learned_weights(&conn, &base).unwrap();
        assert!((weights.w_cap - base.w_cap - MAX_SHIFT).abs() < 1e-10);
        assert!(weights.w_cost >= MIN_W_COST);
    }

    #[test]
    fn null_ratings_are_ignored_and_minimum_cost_is_preserved() {
        let base = Weights {
            w_cap: 0.45,
            w_cost: MIN_W_COST,
            w_lat: 0.25,
            w_ctx: 0.25,
        };
        let conn = connection(&[None, Some(1), Some(2), Some(3)]);
        let (weights, note) = learned_weights(&conn, &base).unwrap();
        assert_same_weights(weights, base);
        assert!(note.is_none());
    }
}
