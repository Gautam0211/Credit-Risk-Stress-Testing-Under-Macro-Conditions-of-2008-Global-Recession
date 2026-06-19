# Credit Risk Model Stress Testing

An end-to-end macroeconomic stress testing framework utilizing Freddie Mac Single-Family Loan datasets.

## Data Warehouse Architecture & Pipeline

Raw multi-million row relational files are processed and aggregated natively within **Snowflake** using the following layout:

```text
[loan_origination] (Static Profile)  ──┐
                                       ├───> [INNER JOIN on loan_identifier] ───> [GROUP BY ALL] ───> Analytical Base Table (ABT)
[loan_servicing] (Monthly Ledger)    ──┘
