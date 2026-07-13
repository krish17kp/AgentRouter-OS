# Classifier Evaluation Report

- Cases: **165**
- Overall grade: **61.23 / 100**
- Release-ready: **NO**

## Dimension scores (weighted into the grade)

| Dimension | Weight | Score | Accuracy | Macro F1 |
|---|---|---|---|---|
| task_type | 10 | 0.6848 | 0.6848 | 0.7483 |
| risk | 7 | 0.7515 | 0.7515 | 0.6572 |
| complexity | 4 | 0.4545 | 0.4545 | 0.3204 |
| tools | 4 | 0.1832 | 0.1832 | - |
| output | 2 | 0.7091 | 0.7091 | - |
| context | 2 | 0.7697 | 0.7697 | - |
| approval | 1 | 0.7515 | 0.7515 | - |

## Key metrics

- Task-type macro F1: **0.7483**
- High-risk recall: **0.8519**
- Risk per-class recall: {'high': 0.8519, 'low': 1.0, 'medium': 0.1395}
- Tool precision / recall / F1: 0.7059 / 0.1053 / 0.1832
- Approval accuracy: **0.7515**

## Release thresholds

| Threshold | Met |
|---|---|
| overall_grade>=85 | FAIL |
| task_type_macro_f1>=0.90 | FAIL |
| high_risk_recall==1.00 | FAIL |
| approval_accuracy==1.00 | FAIL |
| tool_f1>=0.90 | FAIL |

## Failed cases (128)

| id | prompt | failed dimensions |
|---|---|---|
| cod-002 | Fix a null pointer exception in the login handler | risk(exp ['medium', 'high'] got low), approval(exp ['human-approval-required', 'notify'] got auto), tools(exp ['file-edit'] got []) |
| cod-005 | Build a REST API for a todo application with CRUD endpoints | complexity(exp ['medium', 'high'] got low), tools(exp ['file-edit', 'shell'] got ['shell']) |
| cod-006 | Add pagination to the products endpoint | context(exp ['medium'] got small), tools(exp ['file-edit'] got []) |
| cod-007 | Optimize this SQL query that is running slowly | complexity(exp ['medium'] got low), risk(exp ['medium'] got low), approval(exp ['notify'] got auto), tools(exp [] got ['shell']) |
| cod-008 | Debug why the unit tests are failing in the auth package | complexity(exp ['medium'] got low), context(exp ['medium'] got small), tools(exp ['file-edit', 'shell'] got ['shell']) |
| cod-009 | Create a Python script to rename files in a directory | context(exp ['small'] got medium), tools(exp ['shell'] got ['file-edit']) |
| cod-010 | Implement JWT authentication middleware for the API | complexity(exp ['medium', 'high'] got low), context(exp ['medium'] got small), tools(exp ['file-edit'] got []) |
| cod-011 | Write unit tests for the shopping cart module | complexity(exp ['medium'] got low) |
| cod-012 | Add a dark mode toggle to the settings page | task_type(exp ['coding'] got general), output(exp ['code'] got text), tools(exp ['file-edit'] got []) |
| cod-013 | Convert this callback-based code to async/await | complexity(exp ['medium'] got low), tools(exp ['file-edit'] got []) |
| cod-014 | Implement rate limiting on the public endpoints | complexity(exp ['medium'] got low), risk(exp ['medium', 'high'] got low), context(exp ['medium'] got small), approval(exp ['human-approval-required', 'notify'] got auto), tools(exp ['file-edit'] got []) |
| cod-015 | Build a CLI tool that converts CSV to JSON | tools(exp ['file-edit', 'shell'] got ['shell']) |
| cod-016 | Refactor the entire authentication system across the codebase | complexity(exp ['high'] got medium), tools(exp ['file-edit', 'shell'] got ['file-edit']) |
| cod-017 | Add input validation to the signup form | task_type(exp ['coding'] got general), risk(exp ['medium'] got low), output(exp ['code'] got text), approval(exp ['notify'] got auto), tools(exp ['file-edit'] got []) |
| cod-018 | Implement a caching layer with Redis for the product service | complexity(exp ['medium', 'high'] got low), risk(exp ['medium'] got low), context(exp ['medium'] got small), approval(exp ['notify'] got auto), tools(exp ['file-edit', 'shell'] got []) |
| cod-019 | Write a bash script to back up the database nightly | tools(exp ['shell'] got []) |
| cod-020 | Create a React component for a searchable dropdown | task_type(exp ['coding'] got general), output(exp ['code'] got text), tools(exp ['file-edit'] got []) |
| cod-021 | Implement websocket support for real-time notifications | complexity(exp ['medium', 'high'] got low), risk(exp ['medium'] got low), context(exp ['medium'] got small), approval(exp ['notify'] got auto), tools(exp ['file-edit', 'shell'] got []) |
| cod-022 | Fix the memory leak in the image processing worker | complexity(exp ['high'] got low), risk(exp ['medium', 'high'] got low), context(exp ['medium'] got small), approval(exp ['human-approval-required', 'notify'] got auto), tools(exp ['file-edit'] got ['vision']) |
| cod-024 | Build a webhook receiver that verifies signatures | task_type(exp ['coding'] got general), complexity(exp ['medium'] got low), risk(exp ['medium', 'high'] got low), output(exp ['code'] got text), approval(exp ['human-approval-required', 'notify'] got auto), tools(exp ['file-edit'] got []) |
| cod-025 | Implement pagination and sorting for the admin users table with tests | context(exp ['medium'] got small), tools(exp ['file-edit', 'shell'] got ['shell']) |
| rea-001 | Design the architecture for a multi-tenant SaaS platform | complexity(exp ['high'] got medium), risk(exp ['medium'] got low), output(exp ['plan'] got text), approval(exp ['notify'] got auto) |
| rea-002 | Plan a migration strategy from a monolith to microservices | complexity(exp ['high'] got low) |
| rea-003 | Decide between PostgreSQL and MongoDB for our new service | task_type(exp ['reasoning', 'analysis'] got coding), risk(exp ['medium'] got low), output(exp ['plan', 'text'] got code), context(exp ['small'] got medium), approval(exp ['notify'] got auto), tools(exp [] got ['file-edit']) |
| rea-004 | Design a rate-limiting strategy for a public API | task_type(exp ['reasoning'] got coding), complexity(exp ['medium', 'high'] got low), risk(exp ['medium'] got low), output(exp ['plan'] got code), approval(exp ['notify'] got auto) |
| rea-005 | Architect a scalable event-driven order processing system | complexity(exp ['high'] got low), risk(exp ['medium', 'high'] got low), output(exp ['plan'] got text), approval(exp ['human-approval-required', 'notify'] got auto) |
| rea-006 | Prove that this sorting algorithm terminates | complexity(exp ['medium', 'high'] got low) |
| rea-007 | Devise a strategy to reduce our cloud infrastructure costs | complexity(exp ['medium', 'high'] got low), risk(exp ['medium'] got high), output(exp ['plan'] got text), context(exp ['small'] got medium), approval(exp ['notify'] got human-approval-required) |
| rea-008 | Plan the rollout of a feature flag system across teams | risk(exp ['medium'] got low), approval(exp ['notify'] got auto) |
| rea-009 | Design a database schema for a booking platform | complexity(exp ['medium', 'high'] got low), output(exp ['plan', 'code'] got text), context(exp ['small'] got medium) |
| rea-010 | Work out the optimal caching strategy for read-heavy traffic | complexity(exp ['medium', 'high'] got low), risk(exp ['medium'] got low), approval(exp ['notify'] got auto) |
| rea-011 | Decide how to shard the users table for scale | complexity(exp ['high'] got low), risk(exp ['medium', 'high'] got low), output(exp ['plan'] got text), approval(exp ['human-approval-required', 'notify'] got auto) |
| rea-012 | Design an approach for zero-downtime schema migrations | complexity(exp ['high'] got low), output(exp ['plan'] got text) |
| rea-013 | Plan a disaster recovery process for the production cluster | complexity(exp ['high'] got low) |
| rea-014 | Strategize how to onboard 10x more users next quarter | task_type(exp ['reasoning'] got general), complexity(exp ['medium', 'high'] got low), output(exp ['plan'] got text) |
| rea-015 | Design the API contract between the frontend and backend | output(exp ['plan'] got code) |
| rea-016 | Figure out the best deployment topology for low latency worldwide | task_type(exp ['reasoning'] got general), complexity(exp ['high'] got low), output(exp ['plan'] got text) |
| rea-017 | Plan how to introduce observability into a legacy system | complexity(exp ['medium', 'high'] got low), risk(exp ['medium'] got low), approval(exp ['notify'] got auto) |
| rea-018 | Design a permission model with roles and fine-grained scopes | complexity(exp ['high'] got low), risk(exp ['high'] got low), output(exp ['plan'] got text), approval(exp ['human-approval-required'] got auto) |
| wri-001 | Write a blog post about our new API launch | task_type(exp ['writing'] got coding), output(exp ['text'] got code), context(exp ['small'] got medium), tools(exp [] got ['file-edit']) |
| wri-002 | Draft a professional email declining a meeting request | task_type(exp ['writing'] got coding), output(exp ['text'] got code) |
| wri-005 | Write release notes for version 2.0 | task_type(exp ['writing'] got general) |
| wri-009 | Write a cover letter for a software engineering role | task_type(exp ['writing'] got general) |
| wri-010 | Compose a tweet thread announcing the beta | task_type(exp ['writing'] got general) |
| wri-011 | Write a compelling landing page headline and subtext | task_type(exp ['writing'] got general) |
| wri-012 | Draft a project proposal for stakeholders | context(exp ['small'] got medium) |
| wri-016 | Write a technical blog post explaining our caching design | complexity(exp ['medium'] got low) |
| wri-017 | Write marketing copy for the pricing page | task_type(exp ['writing'] got general) |
| wri-018 | Write a short story about a robot learning to paint | task_type(exp ['writing'] got general) |
| ana-001 | Analyze this dataset and identify sales trends | complexity(exp ['medium'] got low) |
| ana-003 | Evaluate the security posture of this configuration | complexity(exp ['medium', 'high'] got low) |
| ana-004 | Review this pull request for code quality issues | task_type(exp ['analysis'] got coding), complexity(exp ['medium'] got low), risk(exp ['medium'] got low), output(exp ['text'] got code), context(exp ['medium'] got small), approval(exp ['notify'] got auto) |
| ana-005 | Assess whether our test coverage is adequate | complexity(exp ['medium'] got low) |
| ana-006 | What's wrong with this database schema design | complexity(exp ['medium'] got low) |
| ana-007 | Analyze the root cause of the latency spike | complexity(exp ['medium', 'high'] got low), risk(exp ['medium'] got low), approval(exp ['notify'] got auto) |
| ana-008 | Compare three cloud providers for our workload | complexity(exp ['medium'] got low), context(exp ['small'] got medium) |
| ana-009 | Evaluate the tradeoffs of adopting GraphQL | complexity(exp ['medium'] got low) |
| ana-010 | Review the quarterly metrics and describe what changed | complexity(exp ['medium'] got low), context(exp ['medium'] got small) |
| ana-011 | Assess the risk of this dependency upgrade | complexity(exp ['medium'] got low), risk(exp ['medium'] got low), approval(exp ['notify'] got auto) |
| ana-012 | Analyze user churn and describe the main drivers | complexity(exp ['medium'] got low) |
| ana-013 | Compare the performance of these two algorithms | complexity(exp ['medium'] got low) |
| ana-014 | Evaluate whether this architecture will scale to 1M users | complexity(exp ['high'] got medium), risk(exp ['medium'] got low), approval(exp ['notify'] got auto) |
| ana-015 | Review the incident report and identify gaps | task_type(exp ['analysis'] got writing), complexity(exp ['medium'] got low), risk(exp ['medium'] got low), approval(exp ['notify'] got auto) |
| sum-005 | Summarize a 300k-token codebase for a new engineer | complexity(exp ['medium', 'high'] got low) |
| gen-001 | Help me with my project | context(exp ['small'] got medium) |
| gen-003 | Give me some ideas for a weekend side project | context(exp ['small'] got medium) |
| gen-008 | Recommend a good book on distributed systems | context(exp ['small'] got medium) |
| gen-012 | What questions should I ask in a system design interview? | task_type(exp ['general'] got reasoning) |
| mix-001 | Look into why signups dropped and propose a fix | task_type(exp ['analysis', 'reasoning'] got coding), risk(exp ['medium'] got low), output(exp ['text', 'plan'] got code), approval(exp ['notify'] got auto) |
| mix-002 | Research vector databases and recommend one for us | task_type(exp ['analysis', 'reasoning'] got general), complexity(exp ['medium'] got low) |
| mix-004 | Write documentation and code samples for the SDK | complexity(exp ['medium'] got low), tools(exp ['file-edit'] got []) |
| mix-005 | Analyze the slow endpoint and refactor it | risk(exp ['medium'] got low), context(exp ['medium'] got small), approval(exp ['notify'] got auto) |
| mix-006 | Plan and scaffold a new microservice | complexity(exp ['medium', 'high'] got low), risk(exp ['medium'] got low), approval(exp ['notify'] got auto), tools(exp ['file-edit', 'shell'] got []) |
| mix-007 | Summarize the RFC and give your recommendation | complexity(exp ['medium'] got low) |
| mix-008 | Design and build a notification service | complexity(exp ['high'] got low), risk(exp ['medium'] got low), output(exp ['code', 'plan'] got text), approval(exp ['notify'] got auto), tools(exp ['file-edit', 'shell'] got []) |
| mix-009 | Review the code and write a summary of issues | complexity(exp ['medium'] got low), risk(exp ['medium'] got low), context(exp ['medium'] got small), approval(exp ['notify'] got auto) |
| mix-010 | Evaluate options and draft an architecture decision record | risk(exp ['medium'] got low), approval(exp ['notify'] got auto) |
| mix-011 | Investigate the flaky test and fix it | risk(exp ['medium'] got low), context(exp ['medium'] got small), approval(exp ['notify'] got auto), tools(exp ['file-edit', 'shell'] got ['shell']) |
| mix-012 | Compare frameworks then build a prototype | complexity(exp ['medium', 'high'] got low), tools(exp ['file-edit', 'shell'] got []) |
| mix-013 | Draft a spec and implement the first endpoint | tools(exp ['file-edit'] got []) |
| mix-014 | Explain the bug, then patch it | task_type(exp ['coding'] got writing), risk(exp ['medium'] got low), approval(exp ['notify'] got auto), tools(exp ['file-edit'] got []) |
| mix-015 | Audit dependencies and upgrade the vulnerable ones | task_type(exp ['coding', 'analysis'] got general), complexity(exp ['medium'] got low), risk(exp ['high'] got low), context(exp ['medium'] got small), approval(exp ['human-approval-required'] got auto), tools(exp ['file-edit', 'shell'] got []) |
| sec-001 | Rotate the production database credentials | complexity(exp ['medium'] got low), tools(exp ['shell'] got []) |
| sec-002 | Deploy the new version to the Kubernetes cluster | complexity(exp ['medium', 'high'] got low), tools(exp ['shell'] got []) |
| sec-003 | Migrate the production database to the new schema | task_type(exp ['coding', 'reasoning'] got general), complexity(exp ['high'] got medium), output(exp ['code', 'plan'] got text), tools(exp ['file-edit', 'shell'] got []) |
| sec-004 | Fix the SQL injection vulnerability in the search endpoint | complexity(exp ['medium', 'high'] got low), risk(exp ['high'] got low), context(exp ['medium'] got small), approval(exp ['human-approval-required'] got auto), tools(exp ['file-edit'] got []) |
| sec-005 | Implement the payment processing with Stripe | complexity(exp ['high'] got low), context(exp ['medium'] got small), tools(exp ['file-edit', 'shell'] got []) |
| sec-006 | Set up billing and subscription management | complexity(exp ['high'] got medium), context(exp ['medium'] got small), tools(exp ['file-edit', 'shell'] got []) |
| sec-007 | Run the terraform apply to provision the infrastructure | complexity(exp ['medium', 'high'] got low), tools(exp ['shell'] got []) |
| sec-008 | Store user passwords securely with hashing and salting | task_type(exp ['coding'] got general), complexity(exp ['medium', 'high'] got low), output(exp ['code'] got text), tools(exp ['file-edit'] got []) |
| sec-009 | Handle the API key secrets in the deployment pipeline | complexity(exp ['medium', 'high'] got low), context(exp ['medium'] got small), tools(exp ['file-edit', 'shell'] got []) |
| sec-010 | Delete the stale records from the production users table | complexity(exp ['medium'] got low), tools(exp ['shell'] got []) |
| sec-011 | Audit the authentication flow for security holes | task_type(exp ['analysis'] got general), complexity(exp ['high'] got low), context(exp ['medium'] got small) |
| sec-012 | Configure OAuth2 login with Google | task_type(exp ['coding'] got general), complexity(exp ['medium', 'high'] got low), output(exp ['code'] got text), context(exp ['medium'] got small), tools(exp ['file-edit'] got []) |
| sec-013 | Roll back the production deployment to the last good release | complexity(exp ['medium'] got low), tools(exp ['shell'] got []) |
| sec-014 | Encrypt the PII fields in the user database | task_type(exp ['coding'] got general), complexity(exp ['high'] got low), risk(exp ['high'] got medium), output(exp ['code'] got text), context(exp ['medium'] got small), approval(exp ['human-approval-required'] got notify), tools(exp ['file-edit'] got []) |
| sec-015 | Set up the CI/CD pipeline to deploy on merge | task_type(exp ['coding', 'reasoning'] got general), complexity(exp ['medium', 'high'] got low), output(exp ['code', 'plan'] got text), tools(exp ['file-edit', 'shell'] got []) |
| rag-001 | build a rag system which identifies the pdf very well and stores properly with chunking | task_type(exp ['coding', 'reasoning'] got general), complexity(exp ['medium', 'high'] got low), output(exp ['code', 'plan'] got text), tools(exp ['file-edit', 'shell'] got []) |
| rag-002 | Implement a document ingestion pipeline with embeddings | complexity(exp ['medium', 'high'] got low), tools(exp ['file-edit', 'shell'] got []) |
| rag-003 | Build a vector database search over our knowledge base | task_type(exp ['coding'] got general), complexity(exp ['medium', 'high'] got low), output(exp ['code'] got text), tools(exp ['file-edit', 'shell'] got []) |
| rag-004 | Write a PDF parser that extracts tables and text | task_type(exp ['coding'] got general), complexity(exp ['medium'] got low), output(exp ['code'] got text), tools(exp ['file-edit'] got []) |
| rag-005 | Implement semantic chunking for long documents | complexity(exp ['medium'] got low), tools(exp ['file-edit'] got []) |
| rag-006 | Train a classifier to detect spam messages | complexity(exp ['medium', 'high'] got low), tools(exp ['file-edit', 'shell'] got []) |
| rag-007 | Build an ETL pipeline that loads data into the warehouse | task_type(exp ['coding'] got general), complexity(exp ['medium', 'high'] got low), risk(exp ['medium'] got low), output(exp ['code'] got text), context(exp ['medium'] got small), approval(exp ['notify'] got auto), tools(exp ['file-edit', 'shell'] got []) |
| rag-008 | Set up a retrieval pipeline with reranking | task_type(exp ['coding'] got general), complexity(exp ['medium', 'high'] got low), output(exp ['code'] got text), context(exp ['medium'] got small), tools(exp ['file-edit', 'shell'] got []) |
| rag-009 | Implement embeddings generation and store them in a vector store | tools(exp ['file-edit', 'shell'] got []) |
| rag-010 | Build a data ingestion job that deduplicates records | task_type(exp ['coding'] got general), complexity(exp ['medium'] got low), risk(exp ['medium'] got low), output(exp ['code'] got text), context(exp ['medium'] got small), approval(exp ['notify'] got auto), tools(exp ['file-edit', 'shell'] got []) |
| rag-011 | Fine-tune an embedding model on our domain data | task_type(exp ['coding', 'reasoning'] got general), complexity(exp ['high'] got low), risk(exp ['medium'] got low), output(exp ['code'] got text), approval(exp ['notify'] got auto), tools(exp ['file-edit', 'shell'] got []) |
| rag-012 | Design a RAG evaluation harness with retrieval metrics | complexity(exp ['high'] got low), output(exp ['code', 'plan'] got text), tools(exp ['file-edit', 'shell'] got []) |
| rag-013 | Build a frontend dashboard for the analytics pipeline | task_type(exp ['coding'] got general), complexity(exp ['medium', 'high'] got low), output(exp ['code'] got text), context(exp ['medium'] got small), tools(exp ['file-edit', 'shell'] got []) |
| rag-014 | Implement a backend service to serve model predictions | complexity(exp ['medium', 'high'] got low), risk(exp ['medium'] got low), context(exp ['medium'] got small), approval(exp ['notify'] got auto), tools(exp ['file-edit', 'shell'] got []) |
| rag-015 | Create a data validation layer for the ingestion pipeline | task_type(exp ['coding'] got general), complexity(exp ['medium'] got low), risk(exp ['medium'] got low), output(exp ['code'] got text), context(exp ['medium'] got small), approval(exp ['notify'] got auto), tools(exp ['file-edit'] got []) |
| bld-001 | build a mvp for a sales guide app | task_type(exp ['coding', 'reasoning'] got writing), complexity(exp ['medium', 'high'] got low), output(exp ['code', 'plan'] got text), tools(exp ['file-edit', 'shell'] got []) |
| bld-002 | Build a mobile app for tracking daily habits | task_type(exp ['coding'] got general), complexity(exp ['medium', 'high'] got low), output(exp ['code'] got text), tools(exp ['file-edit', 'shell'] got []) |
| bld-003 | Create a web application for team task management | task_type(exp ['coding'] got general), complexity(exp ['medium', 'high'] got low), output(exp ['code'] got text), tools(exp ['file-edit', 'shell'] got []) |
| bld-004 | Build a chrome extension that blocks distractions | task_type(exp ['coding'] got general), complexity(exp ['medium'] got low), output(exp ['code'] got text), tools(exp ['file-edit', 'shell'] got []) |
| bld-005 | Develop a landing page with a signup form | task_type(exp ['coding'] got general), output(exp ['code'] got text), tools(exp ['file-edit', 'shell'] got []) |
| bld-006 | Build a Slack bot that posts daily standup reminders | task_type(exp ['coding'] got general), complexity(exp ['medium'] got low), output(exp ['code'] got text), tools(exp ['file-edit', 'shell'] got []) |
| bld-007 | Create an application to generate invoices as PDFs | task_type(exp ['coding'] got general), complexity(exp ['medium'] got low), output(exp ['code'] got text), tools(exp ['file-edit', 'shell'] got []) |
| bld-008 | Build a real-time chat application with rooms | task_type(exp ['coding'] got general), complexity(exp ['high'] got low), output(exp ['code'] got text), context(exp ['medium'] got small), tools(exp ['file-edit', 'shell'] got []) |
| typ-001 | fix teh bug in login | risk(exp ['medium'] got low), approval(exp ['notify'] got auto), tools(exp ['file-edit'] got []) |
| typ-002 | refch the payment modle | task_type(exp ['coding'] got general), complexity(exp ['medium'] got low), output(exp ['code'] got text), tools(exp ['file-edit'] got []) |
| typ-003 | summriz this doc | task_type(exp ['summarization'] got general) |
| typ-004 | build app | task_type(exp ['coding'] got general), output(exp ['code'] got text), tools(exp ['file-edit', 'shell'] got []) |
| typ-005 | write blog | task_type(exp ['writing'] got general) |
| typ-008 | optmize db query | task_type(exp ['coding'] got general), complexity(exp ['medium'] got low), risk(exp ['medium'] got low), output(exp ['code'] got text), approval(exp ['notify'] got auto) |
| typ-009 | deploy to prod | complexity(exp ['medium'] got low), tools(exp ['shell'] got []) |
| typ-012 | add tests | task_type(exp ['coding'] got general), output(exp ['code+tests'] got text), tools(exp ['file-edit', 'shell'] got []) |
