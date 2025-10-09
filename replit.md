# List Point Web App

## Overview
List Point is a minimalistic Flask-based web application designed for creating, managing, and sharing various types of lists. It incorporates social features, such as list discovery and collaboration, alongside robust user authentication and a clean, responsive user interface. The platform aims to provide a flexible and intuitive list-making experience, supporting both permanent item management and dynamic, restorable checklist templates. The business vision is to offer a streamlined list management solution with integrated social functionalities and a sustainable revenue model through subscriptions and advertising.

## User Preferences
I prefer iterative development and want to be involved in key decision-making processes. Please ask for my approval before implementing major changes or new features. I appreciate clear, concise explanations and prefer a modular, well-structured codebase. I am open to suggestions for improvements but want to maintain a focus on core functionality and user experience.

## System Architecture

### UI/UX Decisions
The application features a clean, minimalistic design with a responsive interface built using TailwindCSS. It supports both dark (default) and light modes, with theme preferences persisted. Navigation is streamlined, grouping list management controls for intuitive access. Image uploads incorporate interactive cropping, compression, and visual feedback for an enhanced user experience.

### Technical Implementations
- **Authentication**: Flask-Login handles user registration, login, session management, and password hashing using Werkzeug.
- **Admin Interface**: Secure admin panel for user management. Admins can view all users (excluding password hashes), edit user fields (except passwords), manage roles and groups, and toggle admin status. All admin routes are protected with authorization checks. Access to the admin panel is shown conditionally in the navigation menu based on the user's admin status.
- **List Management**: Supports "Standard Lists" for permanent items and "Check Lists" which act as templates. Check Lists have "Check Off Mode" for temporary checking and "Edit Mode" for permanent template modification. Items are automatically sorted alphabetically.
- **Item Management**: Includes features like click-to-delete, autocomplete suggestions, and an undo system for deleted items.
- **Social Features**: Users can browse, search, and filter public lists, favorite lists, and invite collaborators. Collaborative lists allow shared item management (add, delete, adjust quantity) for both owners and collaborators.
- **Image Handling**: Client-side image cropping and compression (up to 500KB) with a custom file picker and visual feedback. Images are converted to JPEG for optimal compression.
- **Revenue System**: Integrates Google AdSense for ads and Stripe for subscription-based ad removal. Ad display logic intelligently handles ad loading and ensures no whitespace is shown if ads fail to load.

### Feature Specifications
- **User Accounts**: Registration, login, session management.
- **Admin Management**: Admin panel for viewing and managing all users, editing user fields, managing roles and groups. Admin access is role-based with secure route protection.
- **List Creation**: Name, thumbnail, tags, visibility (public/private).
- **List Types**: Standard (permanent) and Check Lists (template-based with two modes).
- **Item Operations**: Add, delete, check/uncheck (for Check Lists), undo.
- **Discovery**: Browse, search, filter lists by tags.
- **Collaboration**: Invite/remove collaborators, shared list access and full item editing capabilities (add, delete, adjust quantity) for collaborators.
- **Favorites**: Mark/unmark lists as favorites for quick access.
- **Theming**: Dark/Light mode toggle with persistence.
- **Image Uploads**: Interactive cropping, compression, aspect ratio control (160/300).
- **Footer Pages**: About Us page describing the platform's mission, features, and solo developer background. Contact Us page with email contact information (kirschnerjohn10@gmail.com).

### System Design Choices
- All items are automatically sorted alphabetically upon addition.
- Check lists store an `original_items` snapshot for restoration.
- `items` in check lists have a `checked` field.
- Image cropping uses a canvas-based interface, maintaining a 160px height / 300px width aspect ratio, with touch and mouse event support.
- Autocomplete cache tracks user's item history for suggestions.
- CSRF protection is enabled on all forms.
- MongoDB indexes are used for performance on frequently queried fields.

## External Dependencies
- **Database**: MongoDB (remote instance via MongoDB Atlas)
- **Payment Processing**: Stripe (for subscriptions and payment management)
- **Advertising**: Google AdSense (for displaying ads)
- **Backend Framework**: Flask
- **Authentication**: Flask-Login
- **Forms**: Flask-WTF
- **MongoDB Driver**: PyMongo
- **Password Hashing**: Werkzeug
- **Image Processing (Python)**: Pillow
- **Frontend Styling**: TailwindCSS (CDN)
- **Client-side Scripting**: Vanilla JavaScript, Fetch API (for AJAX)