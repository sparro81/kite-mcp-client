# Python Kite Model Context Protocol client with Oauth Flow


Zerodha Kite - one of the largest discount brokers in India and very tech advanced released recently the MCP Server. It has given documentation on how to use tools like Claude-Desktop and other thick clients to use the MCP Server - https://zerodha.com/z-connect/featured/connect-your-zerodha-account-to-ai-assistants-with-kite-mcp

But it is not clear how to authenticate from your code. This is hopefully an explanaiton for this and also to understand the authenticaiton part of Model Context Protocol - https://modelcontextprotocol.io/specification/draft/basic/authorization



This folder [kite-mcp-client](kite-mcp-client) holds the flow of the Authenticating with your Kite account (via Oauth https://modelcontextprotocol.io/specification/draft/basic/authorization) using the PKCE flow

The login flow is initiated by calling the 'login' tool and it returns a URL that the user must open in their browser to complete the login process.

The Authentication happens externally via users browser

The flow as I understood is something like below

```
1.FastMCP Client --> SSE Session --> MCP Server (https://mcp.kite.trade/sse)
    2.Session is open with MCP Server and a session id is created here  by the server and kept
        {Inside the session}
            3.MCP Client call login(),
                MCP Server return Login URL with a session id.
                (Example of a stale one https://kite.zerodha.com/connect/login?api_key=kitemcp&v=3&redirect_params=session_id%3D44ce2d96-710b-4442-bf57-cd0d5d0e4050)
            4.User opens Chrome or Firefox and externally authenticates with Kite
            5.Kite MCP Server uses this session id and finds the SSE session which is mapped to this (iternal logic)
                **The MCP server implicitly updates the authentication state of your SSE session**
            6.MCP Client calls other API like `getHoldings` without explicitly sending any access_token
                It doesn't send the access_token itself. Instead, **it sends the getHoldings command over the already authenticated SSE session**.
                The mcp.kite.trade backend, which holds the access_token for that session, then uses it to make the actual call to Zerodha's core Kite API on your behalf. This could be PKCE flow
            7.It gets the result back with the users holding
```

Note that the Access Key for MCP for this 'kitemcp'. This is public. Unlike the regular OAuth flow the Access token is not stored or send in this flow

Note that in this client

- The user must then confirm they have logged in by pressing Enter in the terminal.


A rough diagram

```
+---------------------+     +-----------------+     +-----------------+     +--------------------------+
|  Your FastMCP Client|     |    User's       |     |  Zerodha's MCP  |     |  Zerodha Kite OAuth      |
|  (Python Script)    |     |    Browser      |     |  Service        |     |  Authorization Server    |
|                     |     |                 |     | (mcp.kite.trade)|     | (kite.zerodha.com/connect)|
+---------------------+     +-----------------+     +-----------------+     +--------------------------+
          |                         |                         |                         |
1. call_tool("login", {})           |                         |                         |
          |------------------------>|                         |                         |
          |                         |                         |                         |
          |                         |2. Generates login URL   |                         |
          |<------------------------| (URL with api_key=kitemcp, session_id in redirect_params)
          |                         |                         |                         |
          |3. Display URL to user   |                         |                         |
          |  webbrowser.open(URL)   |                         |                         |
          +------------------------>|                         |                         |
                                    |                         |                         |
                                    |4. User clicks URL,       |                         |
                                    |   logs into Kite          |                         |
                                    |                         |                         |
                                    |                         |                         |
                                    |  --- OAuth Flow (Layer 1) ---                     |
                                    |                         |                         |
                                    |5. Redirects to MCP      |                         |
                                    |   (with request_token   |                         |
                                    |   & session_id)         |                         |
                                    |------------------------>|                         |
                                    |                         |                         |
                                    |                         |6. MCP receives request_token,  |
                                    |                         |   initiates Token Exchange     |
                                    |                         |                                |
                                    |                         |<--- PKCE Step 1: code_challenge sent
                                    |                         |     (from MCP's initial request to Kite)
                                    |                         |------------------------------->|
                                    |                         |                                |
                                    |                         |7. Exchanges request_token      |
                                    |                         |   + code_verifier              |
                                    |                         |   + kitemcp_api_secret         |
                                    |                         |------------------------------->|
                                    |                         |  <--- PKCE Step 2: code_verifier sent
                                    |                         |                                |
                                    |                         |8. Validates PKCE & authenticates|
                                    |                         |<-------------------------------|
                                    |                         |                                |
                                    |                         |  --- OAuth Flow (Layer 1 - END) ---
                                    |                         |9. Stores access_token          |
                                    |                         |   (associated with session_id) |
                                    |                         |                                |
          |                         |                         |10. Notifies FastMCP Client    |
          |<---------------------------------------------------|    (via SSE connection, implicit session update)
          |                         |                         |                                |
          |11. User presses Enter   |                         |                                |
          |   (script proceeds)     |                         |                                |
          |                         |                         |                                |
          |12. call_tool("get_holdings", {})                   |                                |
          |-------------------------------------------------->|                                |
          |                         |                         |13. Uses stored access_token to|
          |                         |                         |    call Kite API              |
          |                         |                         |------------------------------->|
          |                         |                         |<-------------------------------|
          |<--------------------------------------------------|14. Sends holdings data back  |
          |                         |                         |                                |
+---------------------+     +-----------------+     +-----------------+     +--------------------------+
```

                    

## How to run

```
uv run main.py
```

