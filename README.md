# FurConnect 🐾

[![MIT License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub stars](https://img.shields.io/github/stars/furconnect/furconnect.svg)](https://github.com/furconnect/furconnect/stargazers)
[![GitHub issues](https://img.shields.io/github/issues/furconnect/furconnect.svg)](https://github.com/furconnect/furconnect/issues)
[![GitHub forks](https://img.shields.io/github/forks/furconnect/furconnect.svg)](https://github.com/furconnect/furconnect/network)

**Free and Open Source Convention Scheduling Software**

FurConnect is a modern, web-based convention scheduling platform designed to make event planning and attendee navigation seamless. Originally created for furry conventions, it's built to be flexible and welcoming for any type of convention or event.

## ✨ Features

- **📅 Interactive Schedule Display** - Clean, responsive schedule grid with real-time updates
- **🔍 Smart Search & Filtering** - Find events by name, description, or host.
- **📱 Mobile-First Design** - Optimized for smartphones and tablets
- **🏷️ Event Categorization** - Organize events by day, tags, or location.
- **👥 Guest & Presenter Profiles** - Showcase speakers and special guests

## 🛠️ Installation

To get a local copy up and running, follow these simple steps:

1. Clone the repository:
   ```bash
   git clone https://github.com/FurConnect/FurConnect.git
   ```
2. Navigate to the project directory:
   ```bash
   cd FurConnect
   ```
3. Install dependencies (assuming you have Python and pip installed):
   ```bash
   pip install -r requirements.txt
   ```
4. Set up the database (using Django's default SQLite for simplicity, or configure your preferred database):
   ```bash
   python manage.py migrate
   ```
5. Create a superuser to access the login site:
   ```bash
   python manage.py createsuperuser
   ```
6. Run the development server:
   ```bash
   python manage.py runserver
   ```

FurConnect should now be running at `http://127.0.0.1:8000/`.

## 🚀 Usage

Once the application is running:

1. Access the login page (`http://127.0.0.1:8000/login/`) using the superuser account you created.
2. Create Conventions, Convention Days, Panels, Hosts, Rooms, and Tags.
3. The public schedule will be available at the root URL (`http://127.0.0.1:8000/`).

## 👋 Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
