-- ============================================================================
-- 1. ENVIRONMENT SETUP & COMPUTE PROVISIONING
-- ============================================================================

CREATE DATABASE IF NOT EXISTS credit_risk_db;
USE DATABASE credit_risk_db;
USE SCHEMA public;

-- Spin up a Virtual Compute Warehouse
CREATE WAREHOUSE IF NOT EXISTS credit_risk_wh 
    WITH WAREHOUSE_SIZE = 'XSMALL' 
    AUTO_SUSPEND = 60 -- Set to 60 for aggressive cost savings
    AUTO_RESUME = TRUE;
USE WAREHOUSE credit_risk_wh;


-- ============================================================================
-- 2. DDL: TABLE DEFINITIONS
-- ============================================================================

-- Create the 32-column Static Origination Table
CREATE OR REPLACE TABLE loan_origination (
    credit_score                NUMBER,         -- 1
    first_payment_date          NUMBER,         -- 2
    first_time_buyer            VARCHAR(1),     -- 3
    maturity_date               NUMBER,         -- 4
    msa                         NUMBER,         -- 5
    mi_percent                  NUMBER,         -- 6
    number_units                NUMBER,         -- 7
    occupancy_status            VARCHAR(1),     -- 8
    cltv                        NUMBER,         -- 9
    dti                         NUMBER,         -- 10
    original_upb                NUMBER,         -- 11
    ltv                         NUMBER,         -- 12
    original_interest_rate      NUMBER(5,3),    -- 13
    channel                     VARCHAR(1),     -- 14
    ppm                         VARCHAR(1),     -- 15
    amortization_type           VARCHAR(5),     -- 16
    property_state              VARCHAR(2),     -- 17
    property_type               VARCHAR(2),     -- 18
    postal_code                 VARCHAR(5),     -- 19
    loan_sequence_number        VARCHAR(20) PRIMARY KEY, -- 20
    loan_purpose                VARCHAR(1),     -- 21
    original_loan_term          NUMBER,         -- 22
    number_borrowers            NUMBER,         -- 23
    seller_name                 VARCHAR(60),    -- 24
    servicer_name               VARCHAR(60),    -- 25
    super_conforming_flag       VARCHAR(1),     -- 26
    pre_harp_loan_seq_num       VARCHAR(20),    -- 27
    special_eligibility_program VARCHAR(1),     -- 28
    harp_indicator              VARCHAR(1),     -- 29
    property_valuation_method   NUMBER,         -- 30
    interest_only_indicator     VARCHAR(1),     -- 31
    vantage_score_4             NUMBER          -- 32
);

-- Create the 35-column Monthly Time-Series Servicing Table
CREATE OR REPLACE TABLE loan_servicing (
    loan_sequence_number               VARCHAR(20),   -- 1
    reporting_period                   NUMBER,        -- 2
    current_actual_upb                 NUMBER(12,2),  -- 3
    current_loan_delinquency_status    VARCHAR(3),    -- 4
    loan_age                           NUMBER,        -- 5
    remaining_months_to_maturity       NUMBER,        -- 6
    defect_settlement_date             NUMBER,        -- 7
    modification_flag                  VARCHAR(1),    -- 8
    zero_balance_code                  VARCHAR(2),    -- 9
    zero_balance_effective_date        NUMBER,        -- 10
    current_interest_rate              NUMBER(5,3),   -- 11
    current_non_interest_bearing_upb   NUMBER(12,2),  -- 12
    due_date_last_paid_installment     NUMBER,        -- 13
    mi_recoveries                      NUMBER(12,2),  -- 14
    net_sales_proceeds                 VARCHAR(20),   -- 15
    non_mi_recoveries                  NUMBER(12,2),  -- 16
    total_expenses                     NUMBER(12,2),  -- 17
    legal_costs                        NUMBER(12,2),  -- 18
    maintenance_preservation_costs     NUMBER(12,2),  -- 19
    taxes_and_insurance                NUMBER(12,2),  -- 20
    miscellaneous_expenses             NUMBER(12,2),  -- 21
    actual_loss                        NUMBER(12,2),  -- 22
    cumulative_modification_costs      NUMBER(12,2),  -- 23
    interest_rate_step_indicator       VARCHAR(1),    -- 24
    payment_deferral_flag              VARCHAR(1),    -- 25
    estimated_loan_to_value            NUMBER,        -- 26
    zero_balance_removal_upb           NUMBER(12,2),  -- 27
    delinquent_accrued_interest        NUMBER(12,2),  -- 28
    delinquency_due_to_disaster        VARCHAR(1),    -- 29
    borrower_assistance_plan           VARCHAR(1),    -- 30
    current_period_modification_costs  NUMBER(12,2),  -- 31
    current_interest_bearing_upb       NUMBER(12,2),  -- 32
    mi_cancellation_indicator          VARCHAR(1),    -- 33
    servicer_name                      VARCHAR(60),   -- 34
    bankruptcy_cramdown_costs          NUMBER(12,2),  -- 35
    PRIMARY KEY (loan_sequence_number, reporting_period)
);


-- ============================================================================
-- 3. PIPELINE CONFIGURATION & INFRASTRUCTURE
-- ============================================================================

-- Establish pipe format configuration rules
CREATE OR REPLACE FILE FORMAT credit_risk_pipe_format
    TYPE = 'CSV'
    FIELD_DELIMITER = '|'
    RECORD_DELIMITER = '\n'
    SKIP_HEADER = 0
    NULL_IF = ('', 'NULL')
    EMPTY_FIELD_AS_NULL = TRUE
    ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE; -- Bypasses legacy sample file layout errors

-- Create internal cloud staging area container
CREATE OR REPLACE STAGE credit_risk_stage;


-- ============================================================================
-- 4. DATA INGESTION (EXECUTE AFTER UPLOADING FILES TO STAGE)
-- ============================================================================

-- Load all Servicing files positionally from the stage
COPY INTO loan_servicing
FROM @credit_risk_stage
PATTERN = '.*svcg.*\.txt\.gz'
FILE_FORMAT = (FORMAT_NAME = 'credit_risk_pipe_format');

-- Load all Origination files positionally from the stage
COPY INTO loan_origination
FROM @credit_risk_stage
PATTERN = '.*orig.*'
FILE_FORMAT = (FORMAT_NAME = 'credit_risk_pipe_format');


-- ============================================================================
-- 5. QA AUDITS & SANITY TASKS
-- ============================================================================

-- Audit Row & Column Integrity via Metadata
SELECT 
    'LOAN_SERVICING' AS table_name,
    (SELECT COUNT(*) FROM loan_servicing) AS total_rows,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'LOAN_SERVICING' AND table_schema = 'PUBLIC' AND table_catalog = 'CREDIT_RISK_DB') AS total_columns
UNION ALL
SELECT 
    'LOAN_ORIGINATION' AS table_name,
    (SELECT COUNT(*) FROM loan_origination) AS total_rows,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'LOAN_ORIGINATION' AND table_schema = 'PUBLIC' AND table_catalog = 'CREDIT_RISK_DB') AS total_columns;

-- Single-Pass Null-Value Scan: Servicing Table
SELECT 
    COUNT_IF(loan_sequence_number IS NULL) AS null_loan_id,
    COUNT_IF(reporting_period IS NULL) AS null_reporting_period,
    COUNT_IF(current_actual_upb IS NULL) AS null_upb,
    COUNT_IF(current_loan_delinquency_status IS NULL) AS null_delinquency_status,
    COUNT_IF(loan_age IS NULL) AS null_loan_age,
    COUNT_IF(zero_balance_code IS NULL) AS null_zero_balance,
    COUNT_IF(current_interest_rate IS NULL) AS null_interest_rate,
    COUNT_IF(modification_flag IS NULL) AS null_mod_flag,
    COUNT_IF(actual_loss IS NULL) AS null_actual_loss,
    COUNT_IF(net_sales_proceeds IS NULL) AS null_net_sales_proceeds
FROM loan_servicing; 

-- Single-Pass Null-Value Scan: Origination Table
SELECT 
    COUNT_IF(loan_sequence_number IS NULL) AS null_loan_id,
    COUNT_IF(credit_score IS NULL) AS null_credit_score,
    COUNT_IF(first_payment_date IS NULL) AS null_first_pay_date,
    COUNT_IF(original_upb IS NULL) AS null_orig_upb,
    COUNT_IF(original_interest_rate IS NULL) AS null_orig_rate,
    COUNT_IF(dti IS NULL) AS null_dti,
    COUNT_IF(ltv IS NULL) AS null_ltv,
    COUNT_IF(occupancy_status IS NULL) AS null_occupancy,
    COUNT_IF(property_state IS NULL) AS null_state,
    COUNT_IF(first_time_buyer IS NULL) AS null_first_time_buyer
FROM loan_origination;


-- ============================================================================
-- 6. ANALYTICAL BASE TABLE (ABT) TRANSFORMATION LAYER
-- ============================================================================

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