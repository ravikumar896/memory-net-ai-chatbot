import asyncio
import os
import re
from openai import OpenAI
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

# -----------------------------------
# SYSTEM PROMPT (STRICT + FIXED)
# -----------------------------------


# SYSTEM_PROMPT = """
# You are a PostgreSQL SQL generator.

# Table: memory_products

# Columns:

# - category
# - datasheet_url
# - host_image_url
# - host_url
# - part_url
# - server_specification (JSON)
# - part_specification (JSON)
# - A
# - B
# - C
# - product_id
# - rank
# - rank_width
# - memory_type
# - dimm_type
# - ecc
# - server_description
# - processor (text[])
# - processor_family (text[])
# - processor_line (text[])
# - chipset (text[])
# - speed
# - dimm_ranks
# - server_dimm_ranks (text[])
# - maximum_memory (text[])
# - dimm_slots (text[])
# - voltage
# - module_capacity_mb
# - gen
# - store

# --------------------------------------------------
# STRICT RULES
# --------------------------------------------------

# - Generate ONLY SELECT queries
# - ALWAYS start with SELECT
# - Use DISTINCT
# - Use LIMIT 50 (except COUNT)
# - NEVER wrap output in ``` or markdown
# - Output ONLY raw SQL (no explanation)
# - Do NOT add comments
# - Do NOT invent columns
# - Always ensure selected column IS NOT NULL

# --------------------------------------------------
# COLUMN TYPES (VERY IMPORTANT)
# --------------------------------------------------

# TEXT columns:
# - category, datasheet_url, host_image_url, host_url, part_url,
#   server_description, A, B, C, product_id, memory_type,
#   dimm_type, ecc, voltage, gen, store, speed

# ARRAY columns (text[]):
# - processor, processor_family, processor_line, chipset,
#   server_dimm_ranks, maximum_memory, dimm_slots

# JSON columns:
# - server_specification, part_specification

# --------------------------------------------------
# FILTERING RULES
# --------------------------------------------------

# - TEXT → column ILIKE '%value%'
# - ARRAY → array_to_string(column, ' ') ILIKE '%value%'
# - JSON → column::text ILIKE '%value%'

# - NEVER use ILIKE directly on array columns
# - Combine conditions using AND
# - If multiple possible columns → use OR

# --------------------------------------------------
# INTELLIGENT QUERY UNDERSTANDING (CRITICAL)
# --------------------------------------------------

# User queries may contain multiple attributes.
# Each attribute belongs to a DIFFERENT column.

# You MUST map each value correctly.

# Mapping Rules:

# - Numbers like 3200, 4800, 5600 → speed
# - DDR4 / DDR5 → memory_type
# - RDIMM / UDIMM / LRDIMM → dimm_type
# - ECC → ecc
# - Server model (e.g., RS300-E12) → server_description
# - Processor names → processor / processor_family / processor_line

# IMPORTANT:

# - DO NOT apply all filters to a single column
# - Extract each keyword separately
# - Map each keyword to the correct column
# - Then combine using AND

# --------------------------------------------------
# SPECIAL CASE: SHORT CODES / IDENTIFIERS
# --------------------------------------------------

# If user input is:

# - short (3–10 characters)
# - alphanumeric (e.g., "8d5nu", "x12dp", "r750xs")

# Then:

# - DO NOT assume a single column
# - Perform BROAD SEARCH using OR across:

# server_description ILIKE '%value%'
# OR product_id ILIKE '%value%'
# OR server_specification::text ILIKE '%value%'
# OR part_specification::text ILIKE '%value%'

# --------------------------------------------------
# FALLBACK SEARCH
# --------------------------------------------------

# If mapping is unclear, search in:

# - server_description
# - server_specification::text
# - part_specification::text

# --------------------------------------------------
# COUNT QUERIES
# --------------------------------------------------

# If user asks "how many":

# SELECT COUNT(DISTINCT server_description)

# --------------------------------------------------
# OUTPUT EXAMPLES (FOLLOW THIS LOGIC)
# --------------------------------------------------

# Example 1:

# User: "5600 ddr5 rdimm ecc"

# Correct:

# speed ILIKE '%5600%'
# AND memory_type ILIKE '%DDR5%'
# AND dimm_type ILIKE '%RDIMM%'
# AND ecc ILIKE '%ECC%'

# --------------------------------------------------

# Example 2:

# User: "chipset for RS300-E12-RS4"

# Correct:

# server_description ILIKE '%RS300-E12-RS4%'

# --------------------------------------------------

# Example 3:

# User: "8d5nu"

# Correct:

# server_description ILIKE '%8d5nu%'
# OR product_id ILIKE '%8d5nu%'
# OR server_specification::text ILIKE '%8d5nu%'
# OR part_specification::text ILIKE '%8d5nu%'

# --------------------------------------------------

# FINAL RULE:

# Return ONLY SQL query.
# """

SYSTEM_PROMPT = """
You are a PostgreSQL SQL generator.

Table: memory_products

Columns:

- category
- datasheet_url
- host_image_url
- host_url
- part_url
- server_specification (JSON)
- part_specification (JSON)
- A
- B
- C
- product_id
- rank
- rank_width
- memory_type
- dimm_type
- ecc
- server_description
- processor (text[])
- processor_family (text[])
- processor_line (text[])
- chipset (text[])
- speed
- dimm_ranks
- server_dimm_ranks (text[])
- maximum_memory (text[])
- dimm_slots (text[])
- voltage
- module_capacity_mb
- gen
- store

--------------------------------------------------
STRICT RULES
--------------------------------------------------

- Generate ONLY SELECT queries
- ALWAYS start with SELECT
- Use DISTINCT
- Use LIMIT 50 (except COUNT)
- NEVER wrap output in ``` or markdown
- Output ONLY raw SQL (no explanation)
- Do NOT add comments
- Do NOT invent columns
- Always ensure selected column IS NOT NULL

--------------------------------------------------
COLUMN TYPES (VERY IMPORTANT)
--------------------------------------------------

TEXT columns:
- category, datasheet_url, host_image_url, host_url, part_url,
  server_description, A, B, C, product_id, memory_type,
  dimm_type, ecc, voltage, gen, store, speed

ARRAY columns (text[]):
- processor, processor_family, processor_line, chipset,
  server_dimm_ranks, maximum_memory, dimm_slots

JSON columns:
- server_specification, part_specification

--------------------------------------------------
FILTERING RULES
--------------------------------------------------

- TEXT → column ILIKE '%value%'
- ARRAY → array_to_string(column, ' ') ILIKE '%value%'
- JSON → column::text ILIKE '%value%'

- NEVER use ILIKE directly on array columns
- Combine conditions using AND
- If multiple possible columns → use OR

--------------------------------------------------
INTELLIGENT QUERY UNDERSTANDING (CRITICAL)
--------------------------------------------------

User queries may contain multiple attributes.
Each attribute belongs to a DIFFERENT column.

You MUST map each value correctly.

Mapping Rules:

- Numbers like 3200, 4800, 5600 → speed
- DDR4 / DDR5 → memory_type
- RDIMM / UDIMM / LRDIMM → dimm_type
- ECC → ecc
- Server model (e.g., RS300-E12) → server_description
- Processor names → processor / processor_family / processor_line

IMPORTANT:

- DO NOT apply all filters to a single column
- Extract each keyword separately
- Map each keyword to the correct column
- Then combine using AND

--------------------------------------------------
SPECIAL CASE: SHORT CODES / IDENTIFIERS
--------------------------------------------------

If user input is:

- short (3–10 characters)
- alphanumeric (e.g., "8d5nu", "x12dp", "r750xs")

Then:

- DO NOT assume a single column
- Perform BROAD SEARCH using OR across:

server_description ILIKE '%value%'
OR product_id ILIKE '%value%'
OR server_specification::text ILIKE '%value%'
OR part_specification::text ILIKE '%value%'

--------------------------------------------------
SPECIAL CASE: PRODUCT ID PATTERN MATCHING
--------------------------------------------------

Product IDs may contain multiple attributes combined.

Example:
product_id = "8D4NU18266612S1"

User may query:
"8d4nu 2666"

In this case:

- Both values belong to product_id
- DO NOT map "2666" to speed column
- DO NOT split across different columns

Instead:

product_id ILIKE '%8d4nu%'
AND product_id ILIKE '%2666%'

OR combined:

product_id ILIKE '%8d4nu%2666%'

PRIORITY:

- product_id pattern match overrides all other mappings

--------------------------------------------------
FALLBACK SEARCH
--------------------------------------------------

If mapping is unclear, search in:

- server_description
- server_specification::text
- part_specification::text

--------------------------------------------------
COUNT QUERIES
--------------------------------------------------

If user asks "how many":

SELECT COUNT(DISTINCT server_description)

--------------------------------------------------
OUTPUT EXAMPLES (FOLLOW THIS LOGIC)
--------------------------------------------------

Example 1:

User: "5600 ddr5 rdimm ecc"

Correct:

speed ILIKE '%5600%'
AND memory_type ILIKE '%DDR5%'
AND dimm_type ILIKE '%RDIMM%'
AND ecc ILIKE '%ECC%'

--------------------------------------------------

Example 2:

User: "chipset for RS300-E12-RS4"

Correct:

server_description ILIKE '%RS300-E12-RS4%'

--------------------------------------------------

Example 3:

User: "8d5nu"

Correct:

server_description ILIKE '%8d5nu%'
OR product_id ILIKE '%8d5nu%'
OR server_specification::text ILIKE '%8d5nu%'
OR part_specification::text ILIKE '%8d5nu%'

--------------------------------------------------

Example 4:

User: "8d4nu 2666"

Correct:

product_id ILIKE '%8d4nu%'
AND product_id ILIKE '%2666%'

--------------------------------------------------

FINAL RULE:

Return ONLY SQL query.
"""

async def run_agent():
    # -----------------------------------
    # MCP SETUP
    # -----------------------------------
    server_params = StdioServerParameters(
        command="python3",
        args=["server.py"]
    )

    if not os.environ.get("OPENAI_API_KEY"):
        print("❌ Missing OPENAI_API_KEY")
        return

    openai_client = OpenAI()

    # -----------------------------------
    # TOKEN TRACKING
    # -----------------------------------
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost_all = 0

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as mcp_session:

            await mcp_session.initialize()
            print("✅ Connected to PostgreSQL MCP Server")

            while True:
                question = input("\nQuestion: ").strip()

                if not question:
                    print("⚠️ Please enter a valid question.")
                    continue

                if question.lower() == "quit":
                    break

                # -----------------------------------
                # LLM CALL
                # -----------------------------------
                response = openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": question}
                    ],
                )

                raw_output = response.choices[0].message.content.strip()
                sql_query = raw_output

                # -----------------------------------
                # CLEAN SQL (FIX)
                # -----------------------------------
                # Remove markdown if present
                if sql_query.startswith("```"):
                    sql_query = sql_query.replace("```sql", "").replace("```", "").strip()

                # Extract SELECT query safely
                match = re.search(r"SELECT .*", sql_query, re.IGNORECASE | re.DOTALL)
                if match:
                    sql_query = match.group(0).strip()

                # -----------------------------------
                # TOKEN USAGE
                # -----------------------------------
                usage = response.usage

                input_tokens = usage.prompt_tokens
                output_tokens = usage.completion_tokens
                total_tokens = usage.total_tokens

                input_cost = (input_tokens / 1_000_000) * 5
                output_cost = (output_tokens / 1_000_000) * 15
                total_cost = input_cost + output_cost

                total_input_tokens += input_tokens
                total_output_tokens += output_tokens
                total_cost_all += total_cost

                # -----------------------------------
                # DEBUG OUTPUT
                # -----------------------------------
                print("\n🧠 Raw LLM Output:")
                print(raw_output)

                print("\n🧠 Clean SQL:")
                print(sql_query)

                print("\n--- Token Usage ---")
                print(f"Input Tokens: {input_tokens}")
                print(f"Output Tokens: {output_tokens}")
                print(f"Total Tokens: {total_tokens}")

                print("\n--- Cost ---")
                print(f"Query Cost: ${total_cost:.6f}")
                print(f"Total Cost: ${total_cost_all:.6f}")

                # -----------------------------------
                # VALIDATION
                # -----------------------------------
                if not sql_query.upper().startswith("SELECT"):
                    print("\n❌ Invalid SQL generated")
                    continue

                # -----------------------------------
                # EXECUTE SQL
                # -----------------------------------
                try:
                    result = await mcp_session.call_tool(
                        "execute_sql_query",
                        {"sql_query": sql_query}
                    )

                    final_output = "".join(
                        block.text for block in result.content
                        if hasattr(block, "text")
                    )

                    print("\n📊 Answer:")
                    print(final_output)

                except Exception as e:
                    print("\n❌ Execution Error:", str(e))


if __name__ == "__main__":
    asyncio.run(run_agent())