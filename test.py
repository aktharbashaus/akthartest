import json

# --- Load both files ---
with open('variables.json') as f:
    dev = json.load(f)
with open('variablesprd.json') as f:
    prd = json.load(f)

# Adjust if your values sit under "parameters"
dev_p = dev.get('parameters', dev)
prd_p = prd.get('parameters', prd)

shared = {}      # identical in both -> variables.new.json
dev_only = {}    # env-specific -> environmentDefaults dev block
prd_only = {}    # env-specific -> environmentDefaults prd block

all_keys = set(dev_p.keys()) | set(prd_p.keys())

for k in sorted(all_keys):
    in_dev = k in dev_p
    in_prd = k in prd_p

    if in_dev and in_prd:
        if dev_p[k] == prd_p[k]:
            shared[k] = dev_p[k]            # same -> shared
        else:
            dev_only[k] = dev_p[k]          # differs -> env-specific
            prd_only[k] = prd_p[k]
    elif in_dev:
        dev_only[k] = dev_p[k]              # dev only
    else:
        prd_only[k] = prd_p[k]              # prd only

# --- Write shared variables ---
with open('variables.new.json', 'w') as f:
    json.dump({'parameters': shared}, f, indent=2)

# --- Write environment defaults ---
env_defaults = {
    'environmentDetails': {
        'dev': dev_only,
        'prd': prd_only
    }
}
with open('environmentDefaults.new.json', 'w') as f:
    json.dump(env_defaults, f, indent=2)

# --- Summary ---
print(f"Shared keys (-> variables.new.json):        {len(shared)}")
print(f"Dev-specific keys (-> environmentDefaults): {len(dev_only)}")
print(f"Prd-specific keys (-> environmentDefaults): {len(prd_only)}")
print("\nReview variables.new.json and environmentDefaults.new.json before replacing originals.")
