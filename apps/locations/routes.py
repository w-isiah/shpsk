# Assuming the blueprint is imported/defined as blueprint
from apps.locations import blueprint
from flask import render_template, request, redirect, url_for, flash, session
import mysql.connector
from werkzeug.utils import secure_filename
from mysql.connector import Error
from datetime import datetime
import os
import random
import logging
import re
from apps import get_db_connection
from jinja2 import TemplateNotFound

# --- HELPER FUNCTION (KEPT FOR ROUTE_TEMPLATE) ---

# Helper - Extract current page name from request
def get_segment(request):
    try:
        segment = request.path.split('/')[-1]
        if segment == '':
            segment = 'locations'
        return segment
    except:
        return None

# --- CORE CRUD ROUTES ---

import logging
from flask import session, flash, redirect, url_for, render_template, current_app, Blueprint




















@blueprint.route('/managed_locations')
def managed_locations():
    """
    Fetch ALL hierarchical locations and associated room details (if available) 
    from the database, using the parent_location_id column to link to the rooms table.
    """
    # 1. Authentication Check (Kept for general security)
    if 'id' not in session:
        flash("You must be logged in to view this page.", "warning")
        return redirect(url_for('authentication_blueprint.login'))

    locations_list = []

    # 2. Database Operation
    try:
        connection = get_db_connection() # Assuming get_db_connection() is available
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT 
                l1.location_id,
                l1.name AS location_name,
                l1.type AS location_type,
                
                -- l3 is the actual parent location (l1.parent_location_id = l3.location_id)
                l3.name AS parent_name, 
                
                -- Room details are joined using l1.parent_location_id = r.room_id
                r.capacity AS room_capacity,      
                r.description AS room_description 
            FROM locations l1
            
            -- 1. Standard Hierarchy Join (l3 is the true parent)
            LEFT JOIN locations l3 ON l1.parent_location_id = l3.location_id
            
            -- 2. Room Details Join (r is room, joined via l1.parent_location_id)
            LEFT JOIN rooms r ON l1.parent_location_id = r.room_id 
            
            GROUP BY l1.location_id 
            ORDER BY l1.name
        """
        
        # The query requires NO parameters
        cursor.execute(query) 
        locations_list = cursor.fetchall()
        
    except Exception as e:
        current_app.logger.error(f"Database error in managed_locations: {e}", exc_info=True)
        flash(f"Error fetching all locations: A database error occurred.", "danger")
        print(f"DEBUG DB Error: {e}") 
        
    finally:
        # 3. Connection Cleanup
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'connection' in locals() and connection:
            connection.close()

    # 4. Render Template
    return render_template(
        'locations/managed_locations.html',
        locations_list=locations_list,
        segment='locations'
    )













@blueprint.route('/add_location', methods=['GET', 'POST'])
def add_location():
    """
    Handles adding a new location. 
    Parent locations are sourced *only* from the 'rooms' table, with column aliasing.
    The Location Name field is now OPTIONAL.
    """
    
    connection = None
    cursor = None
    parent_locations = []

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. Load data for the form (Parent Locations from the 'rooms' table)
        query = """
            SELECT 
                room_id AS location_id,
                room_name AS name,
                'Room' AS type,
                description
            FROM rooms
            ORDER BY room_name
        """
        cursor.execute(query)
        parent_locations = cursor.fetchall()

        if request.method == 'POST':
            # Location Name is now allowed to be an empty string
            name = request.form.get('name', '').strip()
            location_type = request.form.get('location_type', '').strip()
            parent_location_id = request.form.get('parent_location_id', '') 

            # Convert empty string to None/NULL for the database
            parent_location_id = parent_location_id if parent_location_id else None
            
            # If name is empty, ensure it's None for database insertion (if the column allows NULL)
            # If your database column is NOT NULL, you must handle this by generating a name or stopping.
            # Assuming it allows NULL or you'll handle blank names.
            db_name = name if name else None

            # 2. Validation
            # Removed: if not name...
            if not location_type:
                flash("Location Type is required!", "warning")
            # The regex check is only needed if a name is provided
            elif name and not re.match(r'^[A-Za-z0-9 _-]+$', name):
                flash("Location name must contain only letters, numbers, spaces, dashes, or underscores.", "danger")
            else:
                # 3. Database Operations
                # Check for duplicate ONLY if a name was actually provided
                if db_name:
                    check_query = "SELECT * FROM locations WHERE name = %s"
                    cursor.execute(check_query, (db_name,))
                    existing = cursor.fetchone()

                    if existing:
                        flash(f"Location '{db_name}' already exists.", "warning")
                        # If a name exists, we fall through to re-render the form
                        return render_template("locations/add_location.html", parent_locations=parent_locations)
                
                # Insert the new location into the 'locations' table
                insert_query = "INSERT INTO locations (name, type, parent_location_id) VALUES (%s, %s, %s)"
                cursor.execute(insert_query, (db_name, location_type, parent_location_id))
                connection.commit()
                flash(f"Location '{(db_name or location_type)}' successfully added!", "success")
                return redirect(url_for('locations_blueprint.add_location'))

        # If POST fails validation, execution continues here.
        
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "danger")
        
    except Exception as e:
        flash(f"An unexpected error occurred: {str(e)}", "danger")
        
    finally:
        if cursor: 
            cursor.close()
        if connection: 
            connection.close()

    return render_template("locations/add_location.html", parent_locations=parent_locations)






@blueprint.route('/edit_location/<int:location_id>', methods=['GET', 'POST'])
def edit_location(location_id):
    """Handles editing an existing location."""
    if 'id' not in session:
        flash("You must be logged in to access this page.", "warning")
        return redirect(url_for('authentication_blueprint.login'))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Load all locations for the parent dropdown, excluding the current location itself
    cursor.execute("SELECT location_id, name, type FROM locations WHERE location_id != %s ORDER BY name", (location_id,))
    parent_locations = cursor.fetchall()

    # Retrieve current location data
    cursor.execute("SELECT * FROM locations WHERE location_id = %s", (location_id,))
    location_data = cursor.fetchone()

    if not location_data:
        cursor.close()
        connection.close()
        flash("Location not found.", "danger")
        return redirect(url_for('blueprint.locations')) # Assuming a main list route exists

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        location_type = request.form.get('location_type', '').strip()
        parent_location_id = request.form.get('parent_location_id', '')

        # Convert empty string to None/NULL for the database
        parent_location_id = parent_location_id if parent_location_id else None

        if not name or not location_type:
            flash("Name and Type are required!", "warning")
        else:
            try:
                update_query = """
                    UPDATE locations
                    SET name = %s, type = %s, parent_location_id = %s
                    WHERE location_id = %s
                """
                cursor.execute(update_query, (name, location_type, parent_location_id, location_id))
                connection.commit()
                flash("Location updated successfully!", "success")
                return redirect(url_for('blueprint.locations')) # Redirect to the main list
            except mysql.connector.Error as e:
                flash(f"Database error: {str(e)}", "danger")

    cursor.close()
    connection.close()

    return render_template(
        'locations/edit_location.html',
        parent_locations=parent_locations,
        location_data=location_data,
        segment='locations'
    )

# --------------------------------------------------------------------------------------------------

@blueprint.route('/delete_location/<int:location_id>')
def delete_location(location_id):
    """Deletes a location from the database by its ID."""
    if 'role' not in session or session['role'] not in ['admin', 'super_admin']:
        flash("You do not have permission to perform this action.", "danger")
        return redirect(url_for('blueprint.locations'))
        
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Check if any assets are linked to this location
        cursor.execute('SELECT COUNT(*) FROM fixed_assets WHERE location_id = %s', (location_id,))
        asset_count = cursor.fetchone()[0]
        
        if asset_count > 0:
            flash(f"Cannot delete location. {asset_count} fixed assets are still assigned to it.", "danger")
            return redirect(url_for('blueprint.locations'))

        # Check if any other locations use this location as a parent
        cursor.execute('SELECT COUNT(*) FROM locations WHERE parent_location_id = %s', (location_id,))
        child_count = cursor.fetchone()[0]
        
        if child_count > 0:
            # Since the FOREIGN KEY is ON DELETE SET NULL, we can allow deletion, 
            # but it's safer to warn the user.
            cursor.execute('UPDATE locations SET parent_location_id = NULL WHERE parent_location_id = %s', (location_id,))
            flash(f"Warning: {child_count} sub-locations have been moved to Top Level.", "warning")


        # Delete the location
        cursor.execute('DELETE FROM locations WHERE location_id = %s', (location_id,))
        connection.commit()
        flash("Location deleted successfully.", "success")
        
    except Exception as e:
        flash(f"Error deleting location: {str(e)}", "danger")
        logging.error(f"Error deleting location {location_id}: {e}")
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

    return redirect(url_for('blueprint.locations'))

# --------------------------------------------------------------------------------------------------

@blueprint.route('/<template>')
def route_template(template):
    """Route for serving supporting location templates that don't need database calls."""
    try:
        if not template.endswith('.html'):
            template += '.html'

        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/locations/FILE.html
        return render_template("locations/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except Exception as e:
        logging.error(f"Error serving template {template}: {e}")
        return render_template('home/page-500.html'), 500