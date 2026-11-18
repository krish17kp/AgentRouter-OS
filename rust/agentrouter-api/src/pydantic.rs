//! The scalar coercions used by Pydantic's non-strict request/response fields.

use serde::de::{self, Visitor};
use serde::Deserializer;
use std::fmt;

pub(crate) fn i64<'de, D>(deserializer: D) -> Result<i64, D::Error>
where
    D: Deserializer<'de>,
{
    struct IntegerVisitor;

    impl<'de> Visitor<'de> for IntegerVisitor {
        type Value = i64;

        fn expecting(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
            formatter.write_str("an integer accepted by Pydantic")
        }

        fn visit_bool<E>(self, value: bool) -> Result<Self::Value, E> {
            Ok(i64::from(value))
        }

        fn visit_i64<E>(self, value: i64) -> Result<Self::Value, E> {
            Ok(value)
        }

        fn visit_u64<E>(self, value: u64) -> Result<Self::Value, E>
        where
            E: de::Error,
        {
            i64::try_from(value).map_err(E::custom)
        }

        fn visit_f64<E>(self, value: f64) -> Result<Self::Value, E>
        where
            E: de::Error,
        {
            if value.is_finite()
                && value.fract() == 0.0
                && value >= i64::MIN as f64
                && value < -(i64::MIN as f64)
            {
                Ok(value as i64)
            } else {
                Err(E::custom("value must be an integer"))
            }
        }

        fn visit_str<E>(self, value: &str) -> Result<Self::Value, E>
        where
            E: de::Error,
        {
            parse_integer(value).map_err(E::custom)
        }
    }

    deserializer.deserialize_any(IntegerVisitor)
}

pub(crate) fn boolean<'de, D>(deserializer: D) -> Result<bool, D::Error>
where
    D: Deserializer<'de>,
{
    struct BooleanVisitor;

    impl<'de> Visitor<'de> for BooleanVisitor {
        type Value = bool;

        fn expecting(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
            formatter.write_str("a boolean accepted by Pydantic")
        }

        fn visit_bool<E>(self, value: bool) -> Result<Self::Value, E> {
            Ok(value)
        }

        fn visit_i64<E>(self, value: i64) -> Result<Self::Value, E>
        where
            E: de::Error,
        {
            match value {
                0 => Ok(false),
                1 => Ok(true),
                _ => Err(E::custom("boolean integer must be 0 or 1")),
            }
        }

        fn visit_u64<E>(self, value: u64) -> Result<Self::Value, E>
        where
            E: de::Error,
        {
            match value {
                0 => Ok(false),
                1 => Ok(true),
                _ => Err(E::custom("boolean integer must be 0 or 1")),
            }
        }

        fn visit_f64<E>(self, value: f64) -> Result<Self::Value, E>
        where
            E: de::Error,
        {
            match value {
                0.0 => Ok(false),
                1.0 => Ok(true),
                _ => Err(E::custom("boolean number must be 0 or 1")),
            }
        }

        fn visit_str<E>(self, value: &str) -> Result<Self::Value, E>
        where
            E: de::Error,
        {
            match value.trim().to_ascii_lowercase().as_str() {
                "0" | "off" | "false" | "no" | "n" | "f" => Ok(false),
                "1" | "on" | "true" | "yes" | "y" | "t" => Ok(true),
                _ => Err(E::custom("invalid boolean string")),
            }
        }
    }

    deserializer.deserialize_any(BooleanVisitor)
}

pub(crate) fn parse_integer(value: &str) -> Result<i64, String> {
    let value = value.trim();
    if let Ok(integer) = value.parse::<i64>() {
        return Ok(integer);
    }
    if let Ok(normalized) = normalize_digits(value) {
        if let Ok(integer) = normalized.parse::<i64>() {
            return Ok(integer);
        }
    }

    // Pydantic accepts integral decimal strings but rejects exponent notation
    // and strings with a non-zero fractional part.
    let (whole, fraction) = value
        .split_once('.')
        .ok_or_else(|| "value must be an integer".to_owned())?;
    if fraction.contains('.') || fraction.starts_with(['+', '-']) {
        return Err("value must be an integer".to_owned());
    }
    let whole = normalize_digits(whole)?;
    let fraction = normalize_digits(fraction)?;
    if fraction.is_empty() || fraction.bytes().any(|digit| digit != b'0') {
        return Err("value must be an integer".to_owned());
    }
    whole
        .parse::<i64>()
        .map_err(|_| "integer is outside the supported range".to_owned())
}

fn normalize_digits(value: &str) -> Result<String, String> {
    let (sign, digits) = match value.strip_prefix('-') {
        Some(digits) => ("-", digits),
        None => match value.strip_prefix('+') {
            Some(digits) => ("+", digits),
            None => ("", value),
        },
    };
    let bytes = digits.as_bytes();
    if bytes.is_empty()
        || !bytes.iter().enumerate().all(|(index, byte)| {
            byte.is_ascii_digit()
                || (*byte == b'_'
                    && index > 0
                    && index + 1 < bytes.len()
                    && bytes[index - 1].is_ascii_digit()
                    && bytes[index + 1].is_ascii_digit())
        })
    {
        return Err("value must be an integer".to_owned());
    }
    Ok(format!("{sign}{}", digits.replace('_', "")))
}
