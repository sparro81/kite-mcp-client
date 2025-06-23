import asyncio
import webbrowser
import re
# news api 066812ee48ac40448e0ec0bc53903897

# We are not running a local web server for the redirect_uri with this specific flow.
# The login flow is initiated by calling the 'login' tool and it returns a URL that the user must open in their browser to complete the login process.
# The user must then confirm they have logged in by pressing Enter in the terminal.
import csv

import json

def save_holdings_csv(raw_holdings, path="holdings.csv"):
    """
    raw_holdings: what you get back from client.call_tool("get_holdings", …)
    It’s usually a single TextContent(text='[...]') element, so we detect that,
    json.loads the .text, then write out the real fields.
    """
    # 1) Peel off JSON if it’s wrapped in a TextContent
    if (
        isinstance(raw_holdings, list)
        and len(raw_holdings) == 1
        and hasattr(raw_holdings[0], "text")
    ):
        try:
            holdings = json.loads(raw_holdings[0].text)
        except json.JSONDecodeError as e:
            print(f"⚠️  Could not parse holdings JSON: {e}")
            return
    else:
        # assume it’s already a list of dicts
        holdings = raw_holdings

    if not holdings:
        print("⚠️  No holdings to save.")
        return

    # 2) Write CSV
    fieldnames = ["tradingsymbol", "quantity", "average_price", "last_price"]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for h in holdings:
            writer.writerow({
                "tradingsymbol":  h.get("tradingsymbol", ""),
                "quantity":       h.get("quantity", 0),
                "average_price":  h.get("average_price", 0),
                "last_price":     h.get("last_price", 0),
            })

    print(f"✅ Saved {len(holdings)} holdings to {path}")
    
    
async def main():

    from fastmcp import Client
    from fastmcp.client.transports import SSETransport

    transport = SSETransport(
        url="https://mcp.kite.trade/sse",
        headers={}
    )

    async with Client(transport) as client:
        print("Connected to fastmcp client.")

        # 3. Call the 'login' tool
        print("Calling fastmcp 'login' tool...")
        login_result = await client.call_tool("login", {})
        print("Login result from fastmcp:", login_result)

        # 4. Extract and display the URL to the user

        login_url = None
        if isinstance(login_result, list):
            for item in login_result:
                if getattr(item, "type", "") == "text":
                    text = item.text

                    # 1) Try to grab the Markdown link [Login to Kite](https://...)
                    m = re.search(r"\[Login to Kite\]\((https://kite\.zerodha\.com[^\)]+)\)", text)
                    if m:
                        login_url = m.group(1)
                        break

                    # 2) Fallback: grab the first https://… substring in the text
                    urls = re.findall(r"(https://[^\s\)\]]+)", text)
                    if urls:
                        login_url = urls[0]
                        break

        if not login_url:
            print("❌ Could not extract login URL:\n", login_result)
            return
        else:
            print("🔗 Login URL extracted:", login_url)
            
        if login_url:
            print("\n=======================================================")
            print("  Please open this URL in your browser to login to Kite:")
            print(f"  {login_url}")
            print("=======================================================\n")

            # Open the URL automatically for convenience
            webbrowser.open(login_url)

            # 5. Wait for user confirmation (crucial step for CLI)
            input("Press Enter after you have successfully logged in to Kite in your browser...")
            print("User confirmed login. Attempting to proceed with fastmcp calls.")
            
            print("Session details after login:")
            print(client.session)

            # Give a small buffer time for fastmcp to potentially synchronize or detect the login.
            await asyncio.sleep(2)

            # 6. Call subsequent tools (assuming fastmcp's session is now updated)
            print("Calling fastmcp 'get_holdings' tool...")
            try:
                
                holdings = await client.call_tool("get_holdings", {})
                print("Your holdings:", holdings)
                # save to CSV for the web UI
                save_holdings_csv(holdings, path="holdings.csv")
                print("Holdings written to holdings.csv")
            except Exception as e:
                print(f"Error fetching holdings: {e}")
                print("It's possible the login session wasn't properly established or detected by fastmcp.")
                print("Please ensure you completed the login in the browser.")
        else:
            print("Could not find login URL in fastmcp response.")
            print("If you are already logged in via browser and fastmcp detects it, this step might be skipped or differ.")


if __name__ == "__main__":
    asyncio.run(main())
