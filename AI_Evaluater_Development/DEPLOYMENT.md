# AI Examiner - Hugging Face Spaces Deployment Guide

Since you are deploying the backend to **Hugging Face Spaces**, follow these specific steps to ensure the new authentication and batch features work perfectly.

## 1. Configure Space Secrets (Environment Variables)
Hugging Face Spaces use "Secrets" to manage environment variables. Go to your Space's **Settings** tab, scroll down to **Variables and secrets**, and add the following as **New Secrets**:

*   `JWT_SECRET_KEY`: Set this to a long, random string (e.g., `my-super-secret-key-2024`). **(REQUIRED)**
*   `ADMIN_EMAIL`: Set this to your login email (e.g., `admin@aiexaminer.com`). **(REQUIRED)**
*   `ADMIN_PASSWORD`: Set this to your login password (e.g., `admin123`). **(REQUIRED)**
*   `MONGO_URI`: Your MongoDB connection string.
*   `GEMINI_API_KEYS`: Your comma-separated API keys.

*Note: If you do not set the Admin credentials, the app will default to `admin@aiexaminer.com` and `admin123`.*

## 2. File Storage on Hugging Face
Hugging Face Spaces use **ephemeral storage**. This is perfectly fine for our application! 
When you upload a folder of PDFs, they will be temporarily saved to the Space, evaluated by the AI, the results will be saved permanently to your MongoDB database, and the temporary PDFs will be cleared out when the Space restarts. 

## 3. Reverse Proxy Limits
Hugging Face puts your Space behind their own reverse proxy. While our backend is configured to accept up to 1 GB, Hugging Face's proxy may still impose its own limits on very large single uploads. If you experience upload failures with massive folders, try uploading in smaller batches (e.g., 50-100 PDFs at a time).

## 4. Frontend Configuration
When you build your React frontend to deploy (e.g., on Vercel, Netlify, or similar), make sure your `REACT_APP_API_URL` points to your Hugging Face Space URL (e.g., `https://your-username-your-space-name.hf.space`).
