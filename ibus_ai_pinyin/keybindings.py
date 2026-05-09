MODIFIER_BITS = {
    "control": "CONTROL_MASK",
    "ctrl": "CONTROL_MASK",
    "alt": "MOD1_MASK",
    "mod1": "MOD1_MASK",
    "shift": "SHIFT_MASK",
    "super": "SUPER_MASK",
    "meta": "META_MASK",
    "hyper": "HYPER_MASK",
}


def normalize_key_name(value):
    return str(value or "").strip().lower().replace("_", "-")


def modifier_mask(ibus, modifiers):
    mask = 0
    for modifier in modifiers or []:
        attr = MODIFIER_BITS.get(normalize_key_name(modifier))
        if attr and hasattr(ibus.ModifierType, attr):
            mask |= getattr(ibus.ModifierType, attr)
    return mask


def key_name(ibus, keyval):
    name = ibus.keyval_name(keyval)
    return normalize_key_name(name)


def matches_keybinding(ibus, keyval, state, binding):
    if not binding or not binding.get("enabled", True):
        return False

    expected_key = normalize_key_name(binding.get("key", "space"))
    expected_modifiers = modifier_mask(ibus, binding.get("modifiers", ["Control"]))
    relevant_state = state & modifier_mask(ibus, MODIFIER_BITS.keys())

    return key_name(ibus, keyval) == expected_key and relevant_state == expected_modifiers
