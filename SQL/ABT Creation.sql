USE DATABASE CREDIT_RISK_DB;
USE SCHEMA public;

CREATE OR REPLACE TABLE analytical_base_table AS
SELECT 
    -- Pull baseline application profiles from static originations
    o.*,
    
    -- Extract macroeconomic baseline vintage tracking year
    FLOOR(o.first_payment_date / 100) AS origination_year,

    -- Aggregate longitudinal performance metrics over the loan lifecycle
    MAX(s.loan_age) AS loan_lifespan_months,
    SUM(COALESCE(s.actual_loss, 0)) AS total_actual_loss,
    
    MAX(CASE WHEN s.current_loan_delinquency_status REGEXP '^[0-9]+$' 
             THEN CAST(s.current_loan_delinquency_status AS INT) 
             ELSE 0 END) AS max_delinquency_status,
             
    SUM(CASE WHEN s.current_loan_delinquency_status = '1' THEN 1 ELSE 0 END) AS times_30_days_late,
    SUM(CASE WHEN s.current_loan_delinquency_status = '2' THEN 1 ELSE 0 END) AS times_60_days_late,
    (MAX(s.current_interest_rate) - MIN(s.current_interest_rate)) AS rate_increase_magnitude,
    (MIN(s.current_actual_upb) / o.original_upb) AS final_upb_ratio,
    MAX(CASE WHEN s.modification_flag = 'Y' THEN 1 ELSE 0 END) AS ever_modified,

    -- Classify default indicator target variable (Y Label)
    CASE 
        WHEN MAX(CASE WHEN s.current_loan_delinquency_status REGEXP '^[0-9]+$' 
                      THEN CAST(s.current_loan_delinquency_status AS INT) 
                      ELSE 0 END) >= 3 
             OR MAX(NULLIF(s.zero_balance_code, '')) IN ('03', '06', '09') 
        THEN 1 
        ELSE 0 
    END AS default_indicator

FROM loan_origination o
INNER JOIN loan_servicing s 
    ON o.loan_sequence_number = s.loan_sequence_number
GROUP BY ALL;

-- Quick final row check on model-ready dataset
SELECT COUNT(*), default_indicator FROM analytical_base_table GROUP BY default_indicator;

SELECT 
    (SELECT COUNT(*) FROM analytical_base_table) AS total_rows,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'ANALYTICAL_BASE_TABLE' AND table_schema = 'PUBLIC') AS total_columns;

SELECT * from analytical_base_table limit 1000;


SELECT CURRENT_ACCOUNT();
SELECT CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME();