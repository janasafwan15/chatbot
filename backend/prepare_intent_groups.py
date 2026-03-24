# prepare_intent_groups.py
from pathlib import Path
import pandas as pd

IN_PATH = Path("data/knowledge_base.xlsx")
OUT_PATH = Path("data/knowledge_base_grouped.xlsx")

def group_for_intent(it: str) -> str:
    it = str(it or "").strip()

    # contact
    if it.startswith("contact_") or it == "How_do_I_contact_support":
        return "contact"

    # hours
    if it == "work_hours":
        return "hours"

    # locations / shipping centers
    if it in {"locations", "search_for_a_shipping_center"}:
        return "locations"

    # prepaid
    if it.startswith("prepaid_") or it in {
        "change_to_prepaid", "charge_a_meter", "replace_card_again", "can_the_shipping_fee_be_refunded"
    }:
        return "prepaid"

    # smart meter
    if it.startswith("smart_") or it in {"smart_payment_methods"}:
        return "smart_meter"

    # energy saving
    if it.startswith("saving_"):
        return "energy_saving"

    # billing
    if it in {
        "billing_issue", "bill_payment_methods", "payment_methods",
        "show_my_bills", "read_receipt", "show_balance", "high_consumption_check"
    }:
        return "billing"

    # complaints
    if ("complaint" in it) or ("report" in it) or ("objection" in it) or ("suggestion" in it):
        return "complaints"

    # outages
    if ("outage" in it) or it.startswith("power_") or it == "knowing_about_emergency_outages":
        return "outages"

    # tariff
    if ("tariff" in it) or it in {
        "find_the_approved_tariff", "commercial_to_residential_tariff",
        "change_tariff_request", "tariff_example", "tariff_definition", "tariff_households"
    }:
        return "tariff"

    # installments
    if ("installment" in it) or (it == "reduce_installments"):
        return "installments"

    # e-services
    if it in {"e_service_status", "e_services_list", "how_to_apply_online"}:
        return "e_services"

    # account/security/app login/password
    if ("account" in it) or ("login" in it) or ("password" in it) or it in {
        "Is_my_data_protected", "Is_payment_secure",
        "Difference_between_persona_and_licensed_account?",
        "What_if_I_forgot_my_password", "show_after_logging_in", "change_the_password"
    }:
        return "account_security"

    # app
    if ("app" in it) or ("application" in it) or (it == "How_do_I_download_Hebron_Municipality_app"):
        return "app"

    # customer changes
    if it in {"transfer_ownership", "change_name", "change_phone", "change_address"}:
        return "customer_changes"

    # street lighting
    if it in {"street_light_unit", "party_lights", "move_poles_lines"} or it.startswith("street_lights"):
        return "street_lighting"

    # technical issues (فولت ضعيف، 3 فاز، فصل...)
    if it in {"weak_voltage", "reconnect_after_disconnect", "temporary_disconnect", "convert_1_to_3_phase", "increase_3_phase_capacity"}:
        return "technical_issues"

    # subscriptions / requests / permits / meter moving
    if it in {
        "new_subscription_docs", "general_requirements", "municipality_permit_needed",
        "service_number", "move_subscription", "transfer_subscription_to_person",
        "edit_beneficiary", "move_meter_inside", "move_meter_outside", "move_meter_location",
        "meter_test_request", "spare_parts_check", "i_have_no_service_number"
    }:
        return "subscriptions_requests"

    # default
    return "other"

def main():
    df = pd.read_excel(IN_PATH)

    if "intent" not in df.columns:
        raise RuntimeError("Excel must include column: intent")

    df["intent_group"] = df["intent"].map(group_for_intent)
    df.to_excel(OUT_PATH, index=False)

    print("✅ Saved:", OUT_PATH)
    print("✅ Groups counts:")
    print(df["intent_group"].value_counts())

if __name__ == "__main__":
    main()