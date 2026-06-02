import re


def normalize_message(message: str) -> str:

    #sub.pattern,replacement,string
    message = re.sub('/[A-Za-z0-9@_/.-]+','<path>',message)

    # Step 2: replace UUIDs with <uuid>
    message = re.sub('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}','<uuid>',message)
    #seperates the email with the @ thats why its outside of the brackers 
    message= re.sub('[A-Za-z0-9._-]+@[A-Za-z0-9._-]+','<email>',message)
    # make sure + sign is added when doing these or is causes individual replacements 
    message =  re.sub('[0-9]+','<number>',message)

    return message


# ── Manual tests ──────────────────────────────────────────────────────────────
# Run this file directly to check your work: python normalize.py
# Each assert will raise an error if your output doesn't match the expected string.

if __name__ == "__main__":
     

    # Numbers
    assert normalize_message("User 84729 not found") == "User <number> not found"
    assert normalize_message("Failed after 3 retries") == "Failed after <number> retries"

    # UUIDs
    assert normalize_message("No record for 550e8400-e29b-41d4-a716-446655440000") == \
        "No record for <uuid>"

    # Emails
    assert normalize_message("user@company.com is not authorized") == \
        "<email> is not authorized"

    # File paths (Unix)
    assert normalize_message("Could not open /home/tbo/app/data.csv") == \
        "Could not open <path>"

    # The ordering test — path must consume email and UUID inside it
    assert normalize_message(
        "Failed to open /home/user@company.com/report_550e8400-e29b-41d4-a716-446655440000.csv"
    ) == "Failed to open <path>"

    # Mixed — number and UUID in same message
    assert normalize_message(
        "Attempt 3 failed for job 550e8400-e29b-41d4-a716-446655440000"
    ) == "Attempt <number> failed for job <uuid>"

    print("All tests passed.")
