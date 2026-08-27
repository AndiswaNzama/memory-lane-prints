# Memory Lane Prints

A Flask-based web application for ordering personalised photo prints online — built for South African customers, with PayFast payments, Cloudinary image storage, and email order confirmations baked in.

---

## What is this?

Memory Lane Prints is a photo printing e-commerce platform where customers can upload their photos and place orders for physical prints. It's built with small business in mind simple to run, easy to manage through the admin panel, and built to scale from a local SQLite setup in development all the way to a production Railway deployment.

The idea is simple: people have photos sitting on their phones that deserve to be printed and put on a wall. Memory Lane makes that easy.

---

## Tech Stack

| Layer | Tool |
|---|---|
| Backend | Python / Flask |
| Database | SQLite (dev) / PostgreSQL via Railway (prod) |
| Image Storage | Cloudinary |
| Payments | PayFast (sandbox + live) |
| Email | Gmail SMTP |
| Error Monitoring | Sentry |
| Deployment | Railway |

---

## Features

- Photo upload with Cloudinary storage — no images sitting on your server
- PayFast payment integration with sandbox mode for testing
- Order management through a password-protected admin panel
- Automated email confirmations for orders and shipping updates
- Sentry error monitoring so you know when something breaks in production
- SQLite for local dev, PostgreSQL for production — zero config changes needed

---

## Getting Started

### Prerequisites

Make sure you have the following installed:

- Python 3.9 or higher
- pip
- Git
- A [Cloudinary](https://cloudinary.com) account (free tier works fine)
- A [PayFast](https://www.payfast.co.za) account (sandbox credentials are already included for testing)
- A Gmail account with [App Passwords](https://myaccount.google.com/apppasswords) enabled (requires 2FA)

---

### 1. Clone the repo

```bash
git clone https://github.com/your-username/memory-lane-prints.git
cd memory-lane-prints
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up your environment variables

Copy the example env file and fill in your own values:

```bash
cp .env.example .env
```

Then open `.env` and fill in the following:

```env
FLASK_ENV=development
SECRET_KEY=change-this-to-a-long-random-string

# Cloudinary — grab these from your Cloudinary dashboard
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret

# PayFast — sandbox credentials are already filled in for testing
PAYFAST_MERCHANT_ID=10000100
PAYFAST_MERCHANT_KEY=46f0cd694581a
PAYFAST_PASSPHRASE=
PAYFAST_SANDBOX=true

# Your app URL — keep this as localhost for local dev
APP_URL=http://localhost:5000

# Leave blank for SQLite in development
DATABASE_URL=

# Admin panel — change this before going live!
ADMIN_PASSWORD=change-me

# Gmail SMTP — use an App Password, not your actual Gmail password
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=hello@memorylaneprints.co.za
MAIL_PASSWORD=your-gmail-app-password

# Sentry — leave blank to disable error monitoring locally
SENTRY_DSN=
```

### 5. Run the app

```bash
flask run
```

Visit [http://localhost:5000](http://localhost:5000) and you should be up and running.



## Admin Panel

The admin panel is accessible at `/admin` and is protected by the `ADMIN_PASSWORD` you set in your `.env` file. From here you can manage orders, view uploads, and update shipping statuses.



## PayFast Testing

In development, `PAYFAST_SANDBOX=true` is already set, which means payments will run through PayFast's sandbox environment  no real money changes hands. The sandbox credentials (`10000100` / `46f0cd694581a`) are PayFast's standard test credentials and are safe to commit.

When you're ready to go live:

1. Replace the sandbox credentials with your live PayFast merchant details
2. Set `PAYFAST_SANDBOX=false`
3. Update `APP_URL` to your production domain



## Deploying to Railway

Railway will automatically detect your Flask app and set most things up for you. A few things to do manually:

1. Add a **PostgreSQL plugin** to your Railway project — Railway will automatically set the `DATABASE_URL` environment variable for you.
2. Add all your environment variables from `.env` into Railway's **Variables** tab (skip `DATABASE_URL` since Railway handles that).
3. Update `APP_URL` to your Railway deployment URL (e.g. `https://your-app.up.railway.app`).
4. Set `FLASK_ENV=production` and `PAYFAST_SANDBOX=false` when you're ready to go live.


## Email Setup (Gmail)

To send order confirmation and shipping alert emails through Gmail:

1. Enable **2-Factor Authentication** on your Google account
2. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Create a new App Password for "Mail"
4. Paste that generated password into `MAIL_PASSWORD` in your `.env`



## Error Monitoring with Sentry

If you want to track errors in production (recommended), sign up for a free account at [sentry.io](https://sentry.io), create a new Flask project, and paste the DSN they give you into `SENTRY_DSN` in your `.env`. Leave it blank to disable Sentry entirely — the app runs fine without it.



## Project Structure


memory-lane-prints/
├── app/
│   ├── __init__.py
│   ├── models.py
│   ├── routes/
│   ├── templates/
│   └── static/
├── .env.example
├── .gitignore
├── requirements.txt
├── run.py
└── README.md


## Contributing
This is a personal project but if you spot a bug or have a suggestion, feel free to open an issue or submit a pull request. Just keep it respectful.

## License
This project is private and not licensed for redistribution. If you'd like to use it as a base for your own project, reach out first

## Contact
Built and maintained by Nosizwe Nzama.
For business enquiries: [hello@memorylaneprints.co.za](mailto:hello@memorylaneprints.co.za)
