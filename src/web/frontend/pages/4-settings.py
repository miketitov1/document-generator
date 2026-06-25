import streamlit as st
import requests
from enum import Enum
from typing import Any, cast, get_origin, get_args
from pydantic import ValidationError
from pydantic.fields import FieldInfo

from src.core.data_transformation.transformation_rule import TransformationRule
from src.shared.settings.app_settings import AppSettings, AnyRule

FASTAPI_URL = "http://localhost:8000"
AVAILABLE_RULES = TransformationRule.get_rule_classes()
BASE_RULE_KEYS = {"selected", "old_var_name", "old_header_name", "new_var_name", "new_header_name", "type", "rule_type"}

def fetch_settings() -> dict[str, Any]:
    """Fetches the application settings from the FastAPI backend.

    Returns:
        dict[str, Any]: The parsed JSON settings from the backend. 
            Returns an empty dict if the request fails.
    """
    try:
        response = requests.get(f"{FASTAPI_URL}/settings")
        response.raise_for_status()
        return response.json()
    except (requests.exceptions.RequestException, ValueError) as e:
        st.error(f"Failed to connect to backend API: {e}")
        return {}

def save_settings(settings_data: dict[str, Any]) -> bool:
    """Sends updated settings to the FastAPI backend.

    Args:
        settings_data: The settings data to be saved.

    Returns:
        bool: True if saved successfully, False otherwise.
    """
    try:
        response = requests.post(f"{FASTAPI_URL}/settings", json=settings_data)
        
        if response.status_code == 422:
            try:
                errors = response.json().get("detail", [])
                error_messages = []
                for err in errors:
                    loc = err.get("loc", [])
                    msg = err.get("msg", "Validation constraint violated.")
                    
                    if len(loc) >= 4 and loc[1] == "rules_list":
                        rule_idx = loc[2]
                        field = loc[-1]
                        error_messages.append(f"**Rule #{rule_idx + 1} ({field})**: {msg}")
                    else:
                        error_messages.append(f"**{'.'.join(str(x) for x in loc)}**: {msg}")
                        
                st.error("### ⚠️ Server Validation Failed (422)\n" + "\n".join(f"- {m}" for m in error_messages))
            except Exception:
                st.error(f"Server validation failed (422): {response.text}")
            return False

        response.raise_for_status()
        st.success("Settings saved successfully!")
        return True
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to update settings on the server: {e}")
        return False

def _render_text_field(
    label: str,
    value: str,
    help_text: str | None,
    key: str,
    is_required: bool,
) -> str:
    """Renders a labeled text input in a two-column layout.

    Args:
        label: The base label for the input.
        value: The current value of the input.
        help_text: Tooltip description.
        key: Unique Streamlit key.
        is_required: Whether to append an asterisk to the label.

    Returns:
        The value entered by the user.
    """
    display_label = f"{label} *" if is_required else f"{label} (Optional)"
    col1, col2 = st.columns([3, 7])
    with col1:
        st.write(display_label)
    with col2:
        return st.text_input(
            label=display_label,
            value=value,
            help=help_text,
            key=key,
            label_visibility="collapsed"
        )
    
def _format_enum(x: Enum) -> str:
    """Formats Enum values for display in Streamlit widgets.

    Args:
        x: The Enum member to format.

    Returns:
        The formatted string representation of the Enum.
    """
    if hasattr(x, "label"):
        return str(x.label)
    if isinstance(x.value, tuple) and len(x.value) >= 2:
        return str(x.value[1])
    return str(x.name)

def _is_list_of_enums(annotation: Any) -> bool:
    """Checks if a type annotation represents a list of Enums.

    Args:
        annotation: The type annotation to check.

    Returns:
        True if it is a list of Enums, False otherwise.
    """
    if get_origin(annotation) is list:
        args = get_args(annotation)
        if args and isinstance(args[0], type) and issubclass(args[0], Enum):
            return True
    return False

def _render_extra_fields(rule: AnyRule, field_name: str, field_info: FieldInfo, i: int) -> Any:
    """Dynamically renders UI widgets for extra rule properties.

    Args:
        rule: The rule instance.
        field_name: The name of the field to render.
        field_info: The Pydantic field information.
        i: The index of the rule in the list.

    Returns:
        The value selected or entered by the user.
    """
    current_val = getattr(rule, field_name)
    base_label = field_info.title or field_name.replace("_", " ").title()
    label = f"{base_label} *" if field_info.is_required() else f"{base_label} (Optional)"

    col1, col2 = st.columns([3, 7])
    with col1:
        st.write(label)
    with col2:
        if isinstance(current_val, bool):
            return st.checkbox("", value=current_val, help=field_info.description, key=f"ext_{field_name}_{i}")
            
        elif isinstance(current_val, Enum):
            enum_class = type(current_val)
            options = list(enum_class)
            return st.selectbox(
                label, 
                options=options,
                index=options.index(current_val) if current_val in options else 0,
                format_func=_format_enum,
                help=field_info.description,
                key=f"ext_{field_name}_{i}",
                label_visibility="collapsed"
            )

        elif _is_list_of_enums(field_info.annotation):
            enum_class = get_args(field_info.annotation)[0]
            return st.multiselect(
                label, 
                options=list(enum_class),
                default=current_val,
                format_func=_format_enum,
                help=field_info.description,
                key=f"ext_{field_name}_{i}",
                label_visibility="collapsed"
            )
        else:
            return st.text_input(
                label,
                value=str(current_val) if current_val is not None else "",
                help=field_info.description,
                key=f"ext_{field_name}_{i}",
                label_visibility="collapsed"
            )

def _render_rule_item(rule: AnyRule, i: int) -> tuple[AnyRule, bool]:
    """Renders the UI for a single rule and returns its updated instance and deletion status.

    Args:
        rule: The rule instance.
        i: The index of the rule.

    Returns:
        A tuple containing (updated_rule_instance, is_marked_for_deletion).
    """
    col_expander, col_del = st.columns([9, 1])
    new_rule = rule.model_copy()

    with col_expander:
        label = f"{new_rule.type}: {new_rule.old_var_name} -> {new_rule.new_var_name}"
        with st.expander(label):
            fields_meta = rule.__class__.model_fields
            
            new_rule.selected = st.checkbox("Selected", value=new_rule.selected, key=f"sel_{i}")
            
            new_rule.old_var_name = _render_text_field(
                "Old Var Name",
                new_rule.old_var_name,
                fields_meta["old_var_name"].description,
                f"ov_{i}",
                True
            )

            new_rule.new_var_name = _render_text_field(
                "New Var Name",
                new_rule.new_var_name or "",
                fields_meta["new_var_name"].description,
                f"nv_{i}",
                False
            )

            new_rule.old_header_name = _render_text_field(
                "Old Header Name",
                new_rule.old_header_name,
                fields_meta["old_header_name"].description,
                f"oh_{i}",
                True
            )

            new_rule.new_header_name = _render_text_field(
                "New Header Name",
                new_rule.new_header_name or "",
                fields_meta["new_header_name"].description,
                f"nh_{i}",
                False
            )

            extra_keys = [k for k in fields_meta.keys() if k not in BASE_RULE_KEYS]
            if extra_keys:
                st.divider()
                st.caption(f"_{new_rule.type} Extra Parameters_")
                for field_name in extra_keys:
                    val = _render_extra_fields(new_rule, field_name, fields_meta[field_name], i)
                    setattr(new_rule, field_name, val)
    
    with col_del:
        to_delete = st.checkbox("❌", key=f"del_{i}", help="Delete this rule")

    return new_rule, to_delete

def main() -> None:
    """Main entry point for the Settings page.

    Initializes the Streamlit page configuration, loads settings from session state,
    and renders the transformation rules editor.
    """
    st.set_page_config(page_title="Settings", page_icon="⚙️")
    st.title("⚙️ Application Settings")
    st.write("### Data Transformation Rules")

    if "settings_data" not in st.session_state:
        raw_settings = fetch_settings()
        if raw_settings:
            st.session_state.settings_data = AppSettings.model_validate(raw_settings)
        else:
            st.warning("Failed to load settings.")
            return

    settings_model = st.session_state.settings_data
    rules = settings_model.rules_list

    with st.form("settings_form"):
        updated_rules_with_delete_status: list[tuple[AnyRule, bool]] = []
        if not rules:
            st.info("No transformation rules currently exist.")
        else:
            for i, rule in enumerate(rules):
                updated_rules_with_delete_status.append(_render_rule_item(rule, i))

        st.write("### Add a new rule")
        new_rule_type = st.selectbox("Select Rule Type", list(AVAILABLE_RULES.keys()))
        
        col_add, col_save = st.columns(2)
        with col_add:
            add_clicked = st.form_submit_button("➕ Add Rule")
        with col_save:
            save_clicked = st.form_submit_button("💾 Save All Settings", type="primary")

        if add_clicked:
            rule_cls = AVAILABLE_RULES[new_rule_type]
            new_rule = cast(AnyRule, rule_cls(old_var_name="new_variable", old_header_name="New Header"))
            settings_model.rules_list.append(new_rule)
            st.rerun()

        if save_clicked:
            filtered_rules = [r for r, to_del in updated_rules_with_delete_status if not to_del]
            
            try:
                dumped_payload = settings_model.model_dump()
                dumped_payload["rules_list"] = [r.model_dump() for r in filtered_rules]
                
                AppSettings.model_validate(dumped_payload)
                
                settings_model.rules_list = filtered_rules
                if save_settings(settings_model.model_dump(mode="json")):
                    st.session_state.settings_data = settings_model
                    st.rerun()
                    
            except ValidationError as e:
                error_messages = []
                for err in e.errors():
                    loc = err.get("loc", [])
                    msg = err.get("msg", "Validation constraint violated.")
                    
                    if len(loc) >= 3 and loc[0] == "rules_list":
                        rule_index = int(loc[1])
                        field_name = loc[-1]
                        rule_type = filtered_rules[rule_index].type
                        error_messages.append(
                            f"**Rule #{rule_index + 1} ({rule_type})** - *{field_name}*: {msg}"
                        )
                    else:
                        error_messages.append(msg)
                
                st.error("### ⚠️ Settings Validation Failed\n" + "\n".join(f"- {m}" for m in error_messages))
            except Exception as e:
                st.error(f"An unexpected error occurred during validation: {e}")

if __name__ == "__main__":
    main()
