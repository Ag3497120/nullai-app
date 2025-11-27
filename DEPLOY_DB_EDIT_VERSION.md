# Deploying the Public Knowledge Base Editor

This guide provides instructions for deploying a "lite" version of the NullAI application. This version disables the AI inference engine and provides a public-facing web interface for collaboratively editing the knowledge base.

## Architecture Overview

This deployment uses a combination of free-tier services:

-   **Vercel:** Hosts the React frontend.
-   **Render:** Hosts the "lite" FastAPI backend.
-   **Supabase:** Provides the PostgreSQL database and handles user authentication.

## Step 1: Supabase Project Setup

1.  **Create a Supabase Account:** If you don't have one, sign up at [supabase.com](https://supabase.com).

2.  **Create a New Project:**
    -   Click "New Project" and give it a name (e.g., `nullai-knowledge-base`).
    -   Generate a secure database password and save it somewhere safe.
    -   Wait for the project to be initialized.

3.  **Get Database Connection String:**
    -   Go to **Project Settings** > **Database**.
    -   Under **Connection string**, find the URI that starts with `postgresql://`.
    -   **Important:** Replace the `[YOUR-PASSWORD]` placeholder in the URI with the database password you saved. This full URI will be your `DATABASE_URL` environment variable for the backend.

4.  **Set up Database Schema:**
    -   Go to the **SQL Editor** in the Supabase dashboard.
    -   Click **New query**.
    -   Copy the entire content of `docs/schema.sql` (Note: This file needs to be created) into the query editor and click **RUN**. This will create the `users`, `knowledge_tiles`, and other necessary tables.

5.  **Configure Authentication Providers:**
    -   For **Google**, **GitHub**, and **ORCID**, you must first create an OAuth application on their respective developer platforms.
        -   Google: [Google Cloud Console](https://console.cloud.google.com/)
        -   GitHub: Developer settings in your GitHub profile
        -   ORCID: [ORCID Developer Tools](https://orcid.org/developer-tools)
    -   When creating the OAuth application, you will be asked for an **"Authorized Redirect URI"**. Use the following pattern, replacing `YOUR_RENDER_BACKEND_URL` with the URL your backend will have from Render (you can set a placeholder first and update it later):
        -   Google: `https://YOUR_RENDER_BACKEND_URL/api/oauth/google/callback`
        -   GitHub: `https://YOUR_RENDER_BACKEND_URL/api/oauth/github/callback`
        -   ORCID: `https://YOUR_RENDER_BACKEND_URL/api/oauth/orcid/callback`
    -   Once you create the applications, you will receive a **Client ID** and a **Client Secret** for each provider. Keep these safe.

## Step 2: Deploy Backend to Render

1.  **Fork the Repository:** Fork this GitHub repository to your own account.

2.  **Create a New Web Service on Render:**
    -   Go to your Render dashboard and click **New +** > **Web Service**.
    -   Connect the repository you just forked.
    -   Give your service a name (e.g., `nullai-backend`). Render will generate a public URL based on this.

3.  **Configure Settings:**
    -   **Environment:** Python
    -   **Region:** Choose a region close to you.
    -   **Build Command:** `pip install -r requirements.txt`
    -   **Start Command:** `python backend/create_db.py && uvicorn backend.app.main:app --host 0.0.0.0 --port 80`

4.  **Add Environment Variables:**
    -   Go to the **Environment** tab for your new service.
    -   Add the following environment variables:
        -   `APP_MODE`: `LITE`
        -   `DATABASE_URL`: The full PostgreSQL connection string from Supabase (with your password).
        -   `GOOGLE_CLIENT_ID`: Your Google OAuth Client ID.
        -   `GOOGLE_CLIENT_SECRET`: Your Google OAuth Client Secret.
        -   `GITHUB_CLIENT_ID`: Your GitHub OAuth Client ID.
        -   `GITHUB_CLIENT_SECRET`: Your GitHub OAuth Client Secret.
        -   `ORCID_CLIENT_ID`: Your ORCID Client ID.
        -   `ORCID_CLIENT_SECRET`: Your ORCID Client Secret.
        -   `GOOGLE_REDIRECT_URI`: `https://YOUR_RENDER_BACKEND_URL/api/oauth/google/callback` (use your actual Render URL).
        -   `GITHUB_REDIRECT_URI`: `https://YOUR_RENDER_BACKEND_URL/api/oauth/github/callback` (use your actual Render URL).
        -   `ORCID_REDIRECT_URI`: `https://YOUR_RENDER_BACKEND_URL/api/oauth/orcid/callback` (use your actual Render URL).
        -   `ORCID_SANDBOX`: `false` (for production ORCID).

5.  **Deploy:**
    -   Click **Create Web Service**. Render will build and deploy your application.
    -   If the first deploy fails due to the database not being ready, you can trigger a manual deploy after the service is created.

## Step 3: Deploy Frontend to Vercel

1.  **Create a Vercel Account:** If you don't have one, sign up at [vercel.com](https://vercel.com).

2.  **Create a New Project:**
    -   From your dashboard, click **Add New...** > **Project**.
    -   Import the GitHub repository you forked.

3.  **Configure Project:**
    -   **Framework Preset:** Vercel should automatically detect **Vite**.
    -   **Root Directory:** Set this to `frontend`.
    -   Expand the **Environment Variables** section.

4.  **Add Environment Variable:**
    -   Add a new environment variable:
        -   `VITE_API_URL`: Set this to the public URL of your backend deployed on Render (e.g., `https://nullai-backend.onrender.com`).

5.  **Deploy:**
    -   Click **Deploy**. Vercel will build and deploy your frontend.

## Step 4: Final Check

Once both the frontend and backend are deployed:

1.  Visit your Vercel frontend URL.
2.  You should see the login page with options for Google, GitHub, and ORCID.
3.  Test the login process with one of the providers.
4.  If successful, you should be redirected to the Knowledge Base page and be able to browse and edit tiles.

Your public knowledge base editor is now live!
