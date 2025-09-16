from apps.dorms import blueprint
from flask import render_template, request, redirect, url_for, flash, session
import mysql.connector
from werkzeug.utils import secure_filename
from mysql.connector import Error
from datetime import datetime
import os
import random
import logging
import re  # <-- Add this line
from apps import get_db_connection
from jinja2 import TemplateNotFound



@blueprint.route('/dorms')
def dorms():
    """Fetches all dorms, their associated rooms, and dorm masters (teachers), and renders the manage dorms page."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # SQL query to fetch all dorms with their associated rooms and dorm masters (teachers)
    cursor.execute('''
        SELECT dormitories.dormitory_id, dormitories.name AS dorm_name, dormitories.gender, 
               dormitories.description AS dorm_description, dormitories.dorm_master_id,
               rooms.room_id, rooms.room_name, rooms.capacity AS room_capacity, rooms.description AS room_description,
               teachers.first_name AS teacher_first_name, teachers.last_name AS teacher_last_name
        FROM dormitories
        LEFT JOIN rooms ON dormitories.room_id = rooms.room_id
        LEFT JOIN teachers ON dormitories.dorm_master_id = teachers.teacher_id
    ''')

    dorms = cursor.fetchall()

    # Close the cursor and connection
    cursor.close()
    connection.close()

    return render_template('dorms/dorms.html', dorms=dorms, segment='dorms')





@blueprint.route('/add_dorms', methods=['GET', 'POST'])
def add_dorms():
    """Handles the adding of a new dormitory."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch all rooms and teachers for dropdowns
    cursor.execute('SELECT * FROM rooms')
    rooms = cursor.fetchall()

    cursor.execute('SELECT * FROM teachers')
    teachers = cursor.fetchall()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        gender = request.form.get('gender', '').strip()
        description = request.form.get('description', '').strip()
        dorm_master_id = request.form.get('dorm_master_id', '').strip()
        room_id = request.form.get('room_id', '').strip()

        # Validate required fields
        if not name or not gender or not room_id:
            flash("Please fill out all required fields!", "warning")

        elif dorm_master_id and not dorm_master_id.isdigit():
            flash("Dorm Master ID must be numeric if provided!", "danger")

        else:
            try:
                # Check for existing dorm with same name and gender
                cursor.execute(
                    'SELECT * FROM dormitories WHERE name = %s AND gender = %s',
                    (name, gender)
                )
                if cursor.fetchone():
                    flash("Dormitory already exists with that name and gender!", "warning")

                else:
                    # Check if selected room is already allocated
                    cursor.execute(
                        'SELECT * FROM dormitories WHERE room_id = %s',
                        (room_id,)
                    )
                    if cursor.fetchone():
                        flash("Selected room is already allocated to another dormitory!", "danger")
                    else:
                        # Insert new dormitory
                        cursor.execute(
                            '''
                            INSERT INTO dormitories (name, gender, description, dorm_master_id, room_id)
                            VALUES (%s, %s, %s, %s, %s)
                            ''',
                            (
                                name,
                                gender,
                                description,
                                int(dorm_master_id) if dorm_master_id else None,
                                int(room_id)
                            )
                        )
                        connection.commit()
                        flash("Dormitory successfully added!", "success")
                        return redirect(url_for('dorms_blueprint.dorms'))

            except mysql.connector.Error as err:
                flash(f"Database error: {err}", "danger")

    # Cleanup
    cursor.close()
    connection.close()

    return render_template(
        'dorms/add_dorms.html',
        teachers=teachers,
        rooms=rooms,
        segment='add_dorms'
    )





@blueprint.route('/edit_dorms/<int:dorm_id>', methods=['GET', 'POST'])
def edit_dorms(dorm_id):
    """Handles editing an existing dormitory record."""

    if request.method == 'POST':
        # Get form data
        name = request.form.get('name', '').strip()
        gender = request.form.get('gender', '').strip()
        capacity = request.form.get('capacity', '').strip()
        description = request.form.get('description', '').strip()
        dorm_master_id = request.form.get('dorm_master_id') or None
        room_id = request.form.get('room_id') or None

        # Validate required fields
        if not name or not gender or not capacity:
            flash("Please fill out all required fields!", "warning")
            return redirect(url_for('dorms_blueprint.edit_dorms', dorm_id=dorm_id))

        if not capacity.isdigit():
            flash("Capacity must be a valid number.", "danger")
            return redirect(url_for('dorms_blueprint.edit_dorms', dorm_id=dorm_id))

        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            # Check for duplicate
            cursor.execute("""
                SELECT * FROM dormitories
                WHERE name = %s AND gender = %s AND dormitory_id != %s
            """, (name, gender, dorm_id))
            if cursor.fetchone():
                flash("A dormitory with the same name and gender already exists!", "warning")
                return redirect(url_for('dorms_blueprint.edit_dorms', dorm_id=dorm_id))

            # Update dormitory
            cursor.execute("""
                UPDATE dormitories
                SET name = %s, gender = %s, capacity = %s, description = %s,
                    dorm_master_id = %s, room_id = %s
                WHERE dormitory_id = %s
            """, (name, gender, int(capacity), description or None,
                  dorm_master_id, room_id, dorm_id))
            connection.commit()
            flash("Dormitory updated successfully!", "success")

        except Exception as e:
            flash(f"An error occurred: {e}", "danger")

        finally:
            cursor.close()
            connection.close()

        return redirect(url_for('dorms_blueprint.dorms'))

    else:  # GET request
        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            # Fetch dorm
            cursor.execute("SELECT * FROM dormitories WHERE dormitory_id = %s", (dorm_id,))
            dorm = cursor.fetchone()

            # Fetch teachers for dropdown
            cursor.execute("SELECT teacher_id, first_name, last_name FROM teachers ORDER BY first_name, last_name")
            teachers = cursor.fetchall()

            # Fetch rooms for dropdown
            cursor.execute("SELECT room_id, room_name FROM rooms ORDER BY room_name")
            rooms = cursor.fetchall()

        except Exception as e:
            flash(f"Failed to retrieve data: {e}", "danger")
            dorm, teachers, rooms = None, [], []

        finally:
            cursor.close()
            connection.close()

        if dorm:
            return render_template(
                'dorms/edit_dorms.html',
                dorm=dorm,
                teachers=teachers,
                rooms=rooms,
                segment='dorms'
            )
        else:
            flash("Dormitory not found.", "danger")
            return redirect(url_for('dorms_blueprint.dorms'))









@blueprint.route('/delete_dorms/<int:dormitory_id>')
def delete_dorms(dormitory_id):
    """Deletes a dormitory record from the database."""
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Check if the dormitory exists before deletion
        cursor.execute("SELECT * FROM dormitories WHERE dormitory_id = %s", (dormitory_id,))
        dorm = cursor.fetchone()

        if not dorm:
            flash("Dormitory not found.", "warning")
        else:
            cursor.execute("DELETE FROM dormitories WHERE dormitory_id = %s", (dormitory_id,))
            connection.commit()
            flash("Dormitory deleted successfully.", "success")

    except Exception as e:
        flash(f"An error occurred while deleting the dormitory: {e}", "danger")

    finally:
        if cursor: cursor.close()
        if connection: connection.close()

    return redirect(url_for('dorms_blueprint.dorms'))
   





@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("dorms/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'dorms'

        return segment

    except:
        return None
