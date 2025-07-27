# Substitute Management System

## Overview

This system is designed to simplify and streamline the process of managing substitute teachers. It allows educators and administrators to submit, accept, and track substitute requests efficiently. The system supports user roles, ensuring a tailored experience for teachers, substitutes, and administrators.

## Features

- **Substitute Requests**  
  Teachers can submit requests for substitute coverage by specifying the date, time, and additional details.

- **Request Notifications**  
  Substitute teachers are notified of new requests and can accept them via the system.

- **Substitute Dashboard**  
  Substitutes have a dedicated dashboard displaying the requests they have accepted, including details of assigned tasks.

- **Teacher Dashboard**  
  Teachers can track the status of their submitted requests and review past bookings.

- **Admin Dashboard**  
  Administrators can manage users (teachers and substitutes) and view recent and older substitute requests.

- **User Profiles**  
  Detailed user profiles, including roles, past activity, and associated grades or subjects, for efficient management.

- **Role-Based System**  
  The system recognizes distinct roles (teacher, substitute, admin) and provides tailored access and functionality for each.

## Technologies

This system is built using:
- **Backend**: Python (Flask framework)
- **Frontend**: HTML, CSS, JavaScript (Bootstrap included for some components)
- **Database**: SQLAlchemy for model management with Alembic for migrations

## Database Management

The system uses SQLAlchemy for database ORM and Alembic (via Flask-Migrate) for database migrations:

### Schema Validation

- All database tables and columns are automatically created on application startup
- The system validates the database schema to ensure all required columns exist

### Database Backups

The system includes an automated backup system for the SQLite database:

- **Daily Backup**: Created automatically every day at 1:00 AM
- **Weekly Backup**: Created automatically every Sunday at 2:00 AM
- Backup files are stored in the `instance/backups` directory
- Initial backups are created when the application starts if they don't exist

#### Manual Backup Operations

You can manually create or restore backups using the Python shell:

```python
# Create a daily backup
from backup import create_daily_backup
create_daily_backup()

# Create a weekly backup
from backup import create_weekly_backup
create_weekly_backup()

# Restore from a backup
from backup import restore_from_backup
restore_from_backup('instance/backups/portal_daily_backup.db')  # Restore from daily backup
restore_from_backup('instance/backups/portal_weekly_backup.db')  # Restore from weekly backup
```

For more details, see the `backup.py` and `scheduler.py` files.

### Database Migrations

To manage database schema changes:

1. **Initialize Migrations** (first time only):
   ```
   python init_migrations.py
   ```

2. **Create a Migration** (after changing models):
   ```
   flask db migrate -m "Description of changes"
   ```

3. **Apply Migrations**:
   ```
   flask db upgrade
   ```

4. **Rollback Migrations** (if needed):
   ```
   flask db downgrade
   ```

5. **View Migration History**:
   ```
   flask db history
   ```

For more details, see the `migrations.py` file.

---

This project is a robust solution for educational institutions looking to manage substitute teacher assignments effectively.
