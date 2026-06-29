import streamlit as st
import pandas as pd
import numpy as np
import joblib
import json
import os
import shap
import matplotlib.pyplot as plt

# =====================================================================
# 1. PAGE CONFIGURATION & THEME
# =====================================================================
st.set_page_config(
    page_title="Systemic Credit Underwriting Engine",
    page_icon="",
    layout="wide"  
)

st.markdown("""
    <style>
        .block-container {padding-top: 1.5rem; padding-bottom: 1.5rem; max-width: 95%;}
        .metric-card {background-color: #1e1e1e; padding: 24px; border-radius: 12px; margin-bottom: 15px;}
        div[data-testid="stMetricValue"] {font-size: 2.4rem; font-weight: bold;}
    </style>
""", unsafe_allow_html=True)

st.title("🏛️ Credit Risk Engine: Macro Stress Underwriting Simulator")
st.markdown("---")

# =====================================================================
# 2. PIPELINE ASSET LOADING & SHAP INITIALIZATION
# =====================================================================
@st.cache_resource
def load_models():
    micro_package = joblib.load('micro_model.pkl')
    macro_package = joblib.load('macro_model.pkl')
    
    micro_model = micro_package['model']
    micro_thresh = micro_package['threshold']
    
    macro_model = macro_package['model']
    macro_thresh = macro_package['threshold']
    
    scaler = joblib.load('robust_scaler.pkl')
    power_transformer = joblib.load('pt_boxcox_transformer.joblib')
    categorical_pipeline = joblib.load('categorical_pipeline.pkl')
    
    macro_explainer = shap.TreeExplainer(macro_model)
    
    return micro_model, macro_model, micro_thresh, macro_thresh, scaler, power_transformer, categorical_pipeline, macro_explainer

@st.cache_data
def load_data():
    with open('preprocessing_parameters.json', 'r') as f:
        prep_params = json.load(f)
        
    baseline_profile = {
        'low_card__FIRST_TIME_BUYER_Y': 0.0, 'low_card__PPM_Y': 0.0, 'low_card__OCCUPANCY_STATUS_P': 1.0, 
        'low_card__OCCUPANCY_STATUS_S': 0.0, 'low_card__LOAN_PURPOSE_N': 0.0, 'low_card__LOAN_PURPOSE_P': 0.0, 
        'low_card__CHANNEL_T': 0.0, 'low_card__PROPERTY_TYPE_MH': 0.0, 'low_card__PROPERTY_TYPE_PU': 0.0, 
        'low_card__PROPERTY_TYPE_SF': 1.0, 'high_card__SELLER_NAME': 0.038, 'high_card__SERVICER_NAME': 0.038,   
        'high_card__PROPERTY_STATE': 0.038, 'high_card__POSTAL_CODE': 0.038, 'high_card__MSA': 0.038,
        'remainder__CREDIT_SCORE': 731.0, 'remainder__MI_PERCENT': 0.0, 'remainder__NUMBER_UNITS': 1.0,
        'remainder__CLTV': 78.0, 'remainder__DTI': 36.0, 'remainder__ORIGINAL_UPB': 156000.0,
        'remainder__ORIGINAL_INTEREST_RATE': 6.25, 'remainder__ORIGINAL_LOAN_TERM': 360.0,
        'remainder__NUMBER_BORROWERS': 2.0, 'remainder__RATE_INCREASE_MAGNITUDE': 0.0, 
        'remainder__CSUSHPISA': 180.912, 'remainder__BRMHELOC01': 7.976, 'remainder__MORTGAGE30US': 6.262,
        'remainder__DRSFRMACBS': 1.74, 'remainder__CREDIT_SCORE_IS_MISSING': 0.0, 'remainder__DTI_IS_MISSING': 0.0
    }
    return prep_params, baseline_profile

try:
    (tuned_lgb_micro, tuned_lgb_macro, MICRO_THRESHOLD, MACRO_THRESHOLD, 
     robust_scaler, pt_transformer, categorical_pipeline, macro_tree_explainer) = load_models()
    preprocessing_parameters, baseline_features = load_data()
    
    micro_expected_features = tuned_lgb_micro.feature_name_
    macro_expected_features = tuned_lgb_macro.feature_name_
    scaler_cols = list(robust_scaler.feature_names_in_) if hasattr(robust_scaler, 'feature_names_in_') else list(baseline_features.keys())
    
    target_encoder = categorical_pipeline.named_transformers_['high_card']
    servicer_categories = list(target_encoder.categories_[1])
    servicer_encodings = list(target_encoder.encodings_[1])
    servicer_mapping = dict(zip(servicer_categories, servicer_encodings))
    global_mean_fallback = target_encoder.target_mean_ if hasattr(target_encoder, 'target_mean_') else 0.038

except Exception as e:
    st.error(f"⚠️ Production Pipeline Error loading assets. Details: {e}")
    st.stop()

# =====================================================================
# 3. SPLIT MAIN SCREEN GRID ARCHITECTURE
# =====================================================================
main_left_col, main_right_col = st.columns([2, 3], gap="large")

with main_left_col:
    st.markdown("###  Underwriting Input Desk")
    
    st.markdown("##### **👤 Core Borrower Profile**")
    credit_score = st.number_input("Credit Score (FICO Equivalent)", min_value=300, max_value=850, value=731, step=1)
    cltv = st.slider("Combined Loan-to-Value (CLTV) Ratio (%)", min_value=10.0, max_value=150.0, value=78.0, step=0.1)
    dti = st.slider("Debt-to-Income (DTI) Ratio (%)", min_value=10.0, max_value=100.0, value=36.0, step=0.1)
    
    st.markdown("##### **Deal Structure Controls**")
    num_borrowers = st.radio("Number of Co-Borrowers on Application", options=[1, 2], index=1, horizontal=True)
    loan_purpose_p = st.toggle("Is Loan Purpose Specifically for Refinancing?", value=False)
    
    servicer_name = st.selectbox(
        "Primary Portfolio Servicing Entity",
        options=list(servicer_mapping.keys()) if servicer_mapping else ["CHASE HOME FINANCE LLC", "WELLS FARGO BANK, N.A.", "BAC HOME LOANS SERVICING, LP"],
        index=0
    )
    
    st.markdown("##### **🌪️ Systemic Macroeconomic Sandbox Vectors**")
    csushpisa_val = st.slider("Case-Shiller Home Price Index (CSUSHPISA)", min_value=100.0, max_value=220.0, value=180.912, step=0.5)
    mortgage30_val = st.slider("30-Year Fixed Mortgage Rate (MORTGAGE30US) %", min_value=3.0, max_value=10.0, value=6.262, step=0.1)
    brmheloc_val = st.slider("HELOC / Home Equity Bank Rates (BRMHELOC01) %", min_value=3.0, max_value=12.0, value=7.976, step=0.1)
    drsfrmacbs_val = st.slider("Bank Mortgage Delinquency Rate (DRSFRMACBS) %", min_value=0.5, max_value=9.0, value=1.74, step=0.1)
    
    st.markdown("<br>", unsafe_allow_html=True)
    run_assessment = st.button("🚀 Run Underwriting Risk Assessment", type="primary", use_container_width=True)

with main_right_col:
    st.markdown("### Symmetrical Risk Spectrum Analysis")
    
    if run_assessment:
        full_base = baseline_features.copy()
        full_base['remainder__CREDIT_SCORE'] = float(credit_score)
        full_base['remainder__CLTV'] = float(cltv)
        full_base['remainder__DTI'] = float(dti)
        full_base['remainder__NUMBER_BORROWERS'] = float(num_borrowers)
        full_base['remainder__RATE_INCREASE_MAGNITUDE'] = 0.0
        
        full_base['remainder__CSUSHPISA'] = float(csushpisa_val)
        full_base['remainder__MORTGAGE30US'] = float(mortgage30_val)
        full_base['remainder__BRMHELOC01'] = float(brmheloc_val)
        full_base['remainder__DRSFRMACBS'] = float(drsfrmacbs_val)
        
        encoded_weight = servicer_mapping.get(servicer_name, global_mean_fallback)
        full_base['high_card__SERVICER_NAME'] = float(encoded_weight)
        full_base['low_card__LOAN_PURPOSE_P'] = 1.0 if loan_purpose_p else 0.0
        full_base['low_card__LOAN_PURPOSE_N'] = 0.0 if loan_purpose_p else 1.0
        
        for col in scaler_cols:
            if col not in full_base: full_base[col] = 0.0
                
        df_full = pd.DataFrame([full_base])[scaler_cols]
        
        try:
            for col in ['remainder__ORIGINAL_UPB', 'remainder__CLTV', 'remainder__CREDIT_SCORE', 
                        'remainder__MI_PERCENT', 'remainder__ORIGINAL_INTEREST_RATE', 'remainder__RATE_INCREASE_MAGNITUDE']:
                if col in df_full.columns and 'winsor_bounds' in preprocessing_parameters and col in preprocessing_parameters['winsor_bounds']:
                    df_full[col] = np.clip(df_full[col], preprocessing_parameters['winsor_bounds'][col]['1pct'], preprocessing_parameters['winsor_bounds'][col]['99pct'])

            if 'remainder__ORIGINAL_LOAN_TERM' in df_full.columns:
                df_full['remainder__ORIGINAL_LOAN_TERM'] = np.minimum(df_full['remainder__ORIGINAL_LOAN_TERM'], 360.0)
            if 'remainder__ORIGINAL_UPB' in df_full.columns:
                df_full['remainder__ORIGINAL_UPB'] = np.maximum(df_full['remainder__ORIGINAL_UPB'], 1.0)
                df_full['remainder__ORIGINAL_UPB'] = pt_transformer.transform(df_full[['remainder__ORIGINAL_UPB']].values).flatten()

            for col in ['remainder__MI_PERCENT', 'remainder__RATE_INCREASE_MAGNITUDE']:
                if col in df_full.columns: df_full[col] = np.log1p(np.maximum(df_full[col], 0.0)) 

            full_scaled_array = robust_scaler.transform(df_full)
            df_full_scaled = pd.DataFrame(full_scaled_array, columns=scaler_cols)

        except Exception as transform_error:
            st.error(f"💥 Preprocessing Pipeline Execution Failed: {transform_error}")
            st.stop()

        X_micro_scaled = df_full_scaled[micro_expected_features]
        X_macro_scaled = df_full_scaled[macro_expected_features]
        
        prob_micro = tuned_lgb_micro.predict_proba(X_micro_scaled)[0, 1]
        prob_macro = tuned_lgb_macro.predict_proba(X_macro_scaled)[0, 1]
        
        # --- METRICS OUT ---
        out_col1, out_col2 = st.columns(2, gap="medium")
        with out_col1:
            st.markdown("<div class='metric-card' style='border-left: 6px solid #4a90e2;'>", unsafe_allow_html=True)
            st.metric(label="Micro Baseline Risk", value=f"{prob_micro * 100:.2f}%")
            st.caption(f"Decision Boundary Cutoff: {MICRO_THRESHOLD * 100:.2f}%")
            if prob_micro >= MICRO_THRESHOLD: st.error("🔴 **REJECT APPLICANT**")
            else: st.success("🟢 **CREDIT APPROVED**")
            st.markdown("</div>", unsafe_allow_html=True)
                
        with out_col2:
            st.markdown("<div class='metric-card' style='border-left: 6px solid #ff9f43;'>", unsafe_allow_html=True)
            st.metric(label="Macro-Enriched Risk", value=f"{prob_macro * 100:.2f}%")
            st.caption(f"Decision Boundary Cutoff: {MACRO_THRESHOLD * 100:.2f}%")
            if prob_macro >= MACRO_THRESHOLD: st.error("🔴 **REJECT APPLICANT**")
            else: st.success("🟢 **CREDIT APPROVED**")
            st.markdown("</div>", unsafe_allow_html=True)

        # =====================================================================
        # 4. HIGH-CONTRAST FILTERED UI SHAP ENGINE
        # =====================================================================
        st.markdown("###  Dashboard Input Attribution (Macro Model)")
        st.markdown("Isolates how each specific widget control choice influenced the net macro prediction output:")
        
        try:
            shap_output = macro_tree_explainer(X_macro_scaled)
            raw_shap_values = shap_output.values[0]
            feature_names = X_macro_scaled.columns.tolist()
            
            clean_names = [f.replace('remainder__', '').replace('high_card__', '').replace('low_card__', '') for f in feature_names]
            
            # Master mapping frame
            shap_df = pd.DataFrame({'feature': clean_names, 'value': raw_shap_values})
            
            # FIXED: List containing the exact features exposed on the frontend controls
            dashboard_ui_features = [
                'CREDIT_SCORE', 'CLTV', 'DTI', 'NUMBER_BORROWERS', 
                'LOAN_PURPOSE_P', 'SERVICER_NAME', 'CSUSHPISA', 
                'MORTGAGE30US', 'BRMHELOC01', 'DRSFRMACBS'
            ]
            
            # Filter to keep only the active controls and sort by absolute impact
            shap_df = shap_df[shap_df['feature'].isin(dashboard_ui_features)]
            shap_df['abs_val'] = shap_df['value'].abs()
            shap_df = shap_df.sort_values(by='abs_val', ascending=True)
            
            fig, ax = plt.subplots(figsize=(10, 5))
            fig.patch.set_facecolor('#0e1117')
            ax.set_facecolor('#0e1117')
            
            bar_colors = ['#FF4B4B' if val >= 0 else '#0068C9' for val in shap_df['value']]
            bars = ax.barh(shap_df['feature'], shap_df['value'], color=bar_colors, edgecolor='none', height=0.55)
            
            ax.axvline(x=0, color='#666666', linestyle='--', alpha=0.7, linewidth=1)
            
            for bar, val in zip(bars, shap_df['value']):
                width = bar.get_width()
                label_text = f" {val:+.3f}"
                if val >= 0:
                    ax.text(width + 0.01, bar.get_y() + bar.get_height()/2, label_text, 
                            va='center', ha='left', color='#FFFFFF', fontweight='bold', fontsize=10)
                else:
                    ax.text(width - 0.01, bar.get_y() + bar.get_height()/2, label_text, 
                            va='center', ha='right', color='#FFFFFF', fontweight='bold', fontsize=10)
            
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['bottom'].set_color('#444444')
            ax.spines['left'].set_color('#444444')
            
            ax.tick_params(axis='x', colors='#FFFFFF', labelsize=10)
            ax.tick_params(axis='y', colors='#FFFFFF', labelsize=11, length=0)
            ax.grid(axis='x', color='#333333', linestyle=':', alpha=0.5)
            
            plt.xlabel("SHAP Value (Risk Contribution Margin)", color='#FFFFFF', fontsize=11, fontweight='bold', labelpad=10)
            plt.tight_layout()
            
            st.pyplot(fig)
            plt.close(fig)
            
        except Exception as shap_error:
            st.error(f"💥 Filtered SHAP Engine Rendering Failure: {shap_error}")
            
    else:
        st.info(" Adjust inputs on the left and click 'Run Underwriting Risk Assessment' to calculate dynamic portfolio exposure metrics.")