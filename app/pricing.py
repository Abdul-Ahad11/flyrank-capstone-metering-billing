# app/pricing.py
# All prices are defined in integer "micro-units" to completely avoid floating-point errors.

PRICING = {
    "api_call": 1000,               # e.g., 1000 micro-units per API call
    "input_token": 10,              # Regular input tokens
    "cached_input_token": 2,        # RULE: Cached input tokens are cheaper
    "output_token": 20,             # Regular output tokens
    "reasoning_token": 20,          # RULE: Reasoning tokens are billed as output tokens
}