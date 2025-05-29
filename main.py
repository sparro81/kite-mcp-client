import asyncio
import webbrowser

# We are not running a local web server for the redirect_uri with this specific flow.
# The login flow is initiated by calling the 'login' tool and it returns a URL that the user must open in their browser to complete the login process.
# The user must then confirm they have logged in by pressing Enter in the terminal.

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
        if isinstance(login_result, list) and login_result:
            for item in login_result:
                if hasattr(item, 'type') and item.type == 'text' and 'URL:' in item.text:
                    url_start_index = item.text.find('URL: ') + len('URL: ')
                    login_url = item.text[url_start_index:].strip()
                    break

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
            except Exception as e:
                print(f"Error fetching holdings: {e}")
                print("It's possible the login session wasn't properly established or detected by fastmcp.")
                print("Please ensure you completed the login in the browser.")
        else:
            print("Could not find login URL in fastmcp response.")
            print("If you are already logged in via browser and fastmcp detects it, this step might be skipped or differ.")


if __name__ == "__main__":
    asyncio.run(main())
