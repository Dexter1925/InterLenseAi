<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://ai.google.dev/static/site-assets/images/share-ais-513315318.png" />
</div>

# InternLens AI

## Run in VS Code

Prerequisites: Node.js 18+ and Python 3.10+.

1. Open the extracted folder in VS Code and open its integrated terminal.
2. Install the dependencies:

   ```powershell
   npm install
   python -m pip install -r requirements.txt
   ```

3. Build and start the application:

   ```powershell
   npm run build
   npm start
   ```

4. Open `http://localhost:3000`.

The Node server starts Flask automatically and routes `/api` calls to it. The app has an offline AI fallback, so `GEMINI_API_KEY` is optional. Add it to your environment if you want Gemini-powered responses.
