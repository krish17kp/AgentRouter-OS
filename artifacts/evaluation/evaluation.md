# Classifier Evaluation Report

- Cases: **165**
- Overall grade: **93.76 / 100**
- Release-ready: **YES**

## Dimension scores (weighted into the grade)

| Dimension | Weight | Score | Accuracy | Macro F1 |
|---|---|---|---|---|
| task_type | 10 | 0.9636 | 0.9636 | 0.952 |
| risk | 7 | 1.0 | 1.0 | 1.0 |
| complexity | 4 | 0.7758 | 0.7758 | 0.7642 |
| tools | 4 | 0.99 | 0.99 | - |
| output | 2 | 0.9515 | 0.9515 | - |
| context | 2 | 0.7636 | 0.7636 | - |
| approval | 1 | 1.0 | 1.0 | - |

## Key metrics

- Task-type macro F1: **0.952**
- High-risk recall: **1.0**
- Risk per-class recall: {'high': 1.0, 'low': 1.0, 'medium': 1.0}
- Tool precision / recall / F1: 1.0 / 0.9802 / 0.99
- Approval accuracy: **1.0**

## Release thresholds

| Threshold | Met |
|---|---|
| overall_grade>=85 | PASS |
| task_type_macro_f1>=0.90 | PASS |
| high_risk_recall==1.00 | PASS |
| approval_accuracy==1.00 | PASS |
| tool_f1>=0.90 | PASS |

## Failed cases (66)

| id | prompt | failed dimensions |
|---|---|---|
| cod-004 | Write a regex that matches valid email addresses | task_type(exp ['coding'] got writing), output(exp ['code'] got text) |
| cod-006 | Add pagination to the products endpoint | context(exp ['medium'] got small) |
| cod-007 | Optimize this SQL query that is running slowly | complexity(exp ['medium'] got low) |
| cod-008 | Debug why the unit tests are failing in the auth package | complexity(exp ['medium'] got low), context(exp ['medium'] got small) |
| cod-009 | Create a Python script to rename files in a directory | complexity(exp ['low'] got medium), context(exp ['small'] got medium) |
| cod-010 | Implement JWT authentication middleware for the API | context(exp ['medium'] got small) |
| cod-011 | Write unit tests for the shopping cart module | complexity(exp ['medium'] got low) |
| cod-013 | Convert this callback-based code to async/await | complexity(exp ['medium'] got low) |
| cod-014 | Implement rate limiting on the public endpoints | context(exp ['medium'] got small) |
| cod-018 | Implement a caching layer with Redis for the product service | context(exp ['medium'] got small) |
| cod-021 | Implement websocket support for real-time notifications | context(exp ['medium'] got small) |
| cod-022 | Fix the memory leak in the image processing worker | complexity(exp ['high'] got low), context(exp ['medium'] got small) |
| cod-025 | Implement pagination and sorting for the admin users table with tests | context(exp ['medium'] got small) |
| rea-006 | Prove that this sorting algorithm terminates | output(exp ['text'] got plan) |
| rea-008 | Plan the rollout of a feature flag system across teams | context(exp ['small'] got medium) |
| rea-011 | Decide how to shard the users table for scale | complexity(exp ['high'] got medium) |
| rea-013 | Plan a disaster recovery process for the production cluster | complexity(exp ['high'] got medium) |
| rea-016 | Figure out the best deployment topology for low latency worldwide | complexity(exp ['high'] got medium) |
| rea-018 | Design a permission model with roles and fine-grained scopes | complexity(exp ['high'] got medium) |
| wri-012 | Draft a project proposal for stakeholders | context(exp ['small'] got medium) |
| wri-016 | Write a technical blog post explaining our caching design | complexity(exp ['medium'] got low) |
| ana-004 | Review this pull request for code quality issues | context(exp ['medium'] got small) |
| ana-005 | Assess whether our test coverage is adequate | context(exp ['medium'] got small) |
| ana-009 | Evaluate the tradeoffs of adopting GraphQL | complexity(exp ['medium'] got low) |
| ana-010 | Review the quarterly metrics and describe what changed | context(exp ['medium'] got small) |
| sum-005 | Summarize a 300k-token codebase for a new engineer | complexity(exp ['medium', 'high'] got low) |
| sum-012 | Summarize the API documentation into a cheat sheet | context(exp ['medium'] got small) |
| gen-001 | Help me with my project | context(exp ['small'] got medium) |
| gen-003 | Give me some ideas for a weekend side project | context(exp ['small'] got medium) |
| gen-008 | Recommend a good book on distributed systems | task_type(exp ['general'] got reasoning), complexity(exp ['low'] got high), output(exp ['text'] got plan), context(exp ['small'] got medium) |
| gen-012 | What questions should I ask in a system design interview? | task_type(exp ['general'] got reasoning), complexity(exp ['low'] got medium), output(exp ['text'] got plan), context(exp ['small'] got medium) |
| mix-002 | Research vector databases and recommend one for us | output(exp ['text'] got plan) |
| mix-004 | Write documentation and code samples for the SDK | complexity(exp ['medium'] got low) |
| mix-005 | Analyze the slow endpoint and refactor it | context(exp ['medium'] got small) |
| mix-007 | Summarize the RFC and give your recommendation | complexity(exp ['medium'] got low), context(exp ['medium'] got small) |
| mix-009 | Review the code and write a summary of issues | complexity(exp ['medium'] got low), context(exp ['medium'] got small) |
| mix-011 | Investigate the flaky test and fix it | output(exp ['code', 'code+tests'] got text), context(exp ['medium'] got small) |
| mix-013 | Draft a spec and implement the first endpoint | complexity(exp ['medium'] got high) |
| mix-015 | Audit dependencies and upgrade the vulnerable ones | context(exp ['medium'] got small) |
| sec-001 | Rotate the production database credentials | complexity(exp ['medium'] got low) |
| sec-002 | Deploy the new version to the Kubernetes cluster | complexity(exp ['medium', 'high'] got low) |
| sec-003 | Migrate the production database to the new schema | complexity(exp ['high'] got medium) |
| sec-004 | Fix the SQL injection vulnerability in the search endpoint | complexity(exp ['medium', 'high'] got low), context(exp ['medium'] got small) |
| sec-005 | Implement the payment processing with Stripe | complexity(exp ['high'] got low), context(exp ['medium'] got small) |
| sec-006 | Set up billing and subscription management | task_type(exp ['coding'] got general), complexity(exp ['high'] got low), output(exp ['code'] got text), context(exp ['medium'] got small), tools(exp ['file-edit', 'shell'] got []) |
| sec-007 | Run the terraform apply to provision the infrastructure | complexity(exp ['medium', 'high'] got low) |
| sec-009 | Handle the API key secrets in the deployment pipeline | complexity(exp ['medium', 'high'] got low), context(exp ['medium'] got small) |
| sec-010 | Delete the stale records from the production users table | complexity(exp ['medium'] got low) |
| sec-011 | Audit the authentication flow for security holes | complexity(exp ['high'] got medium), context(exp ['medium'] got small) |
| sec-012 | Configure OAuth2 login with Google | complexity(exp ['medium', 'high'] got low), context(exp ['medium'] got small) |
| sec-013 | Roll back the production deployment to the last good release | complexity(exp ['medium'] got low) |
| sec-014 | Encrypt the PII fields in the user database | complexity(exp ['high'] got low), context(exp ['medium'] got small) |
| rag-003 | Build a vector database search over our knowledge base | context(exp ['medium'] got small) |
| rag-006 | Train a classifier to detect spam messages | complexity(exp ['medium', 'high'] got low) |
| rag-007 | Build an ETL pipeline that loads data into the warehouse | context(exp ['medium'] got small) |
| rag-008 | Set up a retrieval pipeline with reranking | context(exp ['medium'] got small) |
| rag-009 | Implement embeddings generation and store them in a vector store | complexity(exp ['medium'] got high) |
| rag-010 | Build a data ingestion job that deduplicates records | context(exp ['medium'] got small) |
| rag-013 | Build a frontend dashboard for the analytics pipeline | context(exp ['medium'] got small) |
| rag-014 | Implement a backend service to serve model predictions | context(exp ['medium'] got small) |
| rag-015 | Create a data validation layer for the ingestion pipeline | context(exp ['medium'] got small) |
| bld-008 | Build a real-time chat application with rooms | context(exp ['medium'] got small) |
| typ-002 | refch the payment modle | task_type(exp ['coding'] got general), complexity(exp ['medium'] got low), output(exp ['code'] got text) |
| typ-005 | write blog | task_type(exp ['writing'] got general) |
| typ-008 | optmize db query | complexity(exp ['medium'] got low) |
| typ-009 | deploy to prod | complexity(exp ['medium'] got low) |
