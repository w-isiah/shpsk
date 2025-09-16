from apps.term import blueprint
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


from flask import request, render_template, flash
from datetime import datetime
import pytz, json


def get_kampala_time():
    """Returns the current datetime in the Africa/Kampala timezone."""
    return datetime.now(pytz.timezone("Africa/Kampala"))


@blueprint.route('/term')
def term():
    """Fetches all terms with year name and renders the manage term page."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Join terms with years to get year_name
    cursor.execute('''
        SELECT t.term_id, t.term_name, t.start_on, t.ends_on,
               t.year_id, y.year_name, t.status
        FROM terms t
        LEFT JOIN study_year y ON t.year_id = y.year_id
    ''')
    terms = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template('term/term.html', terms=terms, segment='term')











@blueprint.route('/add_term', methods=['GET', 'POST'])
def add_term():
    """Fetches all study_years and renders the manage study_years page."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch all study_years from the database
    cursor.execute('SELECT * FROM study_year')
    study_years = cursor.fetchall()
    """Handles adding a new term and logs the action with Kampala timestamp."""
    if request.method == 'POST':
        term_name = request.form.get('term_name')
        start_on = request.form.get('start_on')
        ends_on = request.form.get('ends_on')
        year_id = request.form.get('year_id') or None  # Optional, may come from a dropdown
        status = request.form.get('status', 0)

        # Basic Validation
        if not term_name or not start_on or not ends_on:
            flash("Please fill out all required fields!", "warning")
        elif len(term_name) > 20:
            flash("Term name must not exceed 20 characters!", "danger")
        else:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            try:
                # Check if the term already exists
                cursor.execute('''
                    SELECT * FROM terms 
                    WHERE term_name = %s AND start_on = %s AND ends_on = %s
                ''', (term_name, start_on, ends_on))
                existing_term = cursor.fetchone()

                if existing_term:
                    flash("A term with the same name and dates already exists!", "warning")
                else:
                    # Insert the term
                    cursor.execute('''
                        INSERT INTO terms (term_name, start_on, ends_on, year_id, status)
                        VALUES (%s, %s, %s, %s, %s)
                    ''', (term_name, start_on, ends_on, year_id, status))
                    connection.commit()

                    term_id = cursor.lastrowid  # Get the newly inserted term_id

                    # Prepare log data
                    new_value = {
                        'term_name': term_name,
                        'start_on': start_on,
                        'ends_on': ends_on,
                        'year_id': year_id,
                        'status': status
                    }

                    # Log to term_logs
                    cursor.execute('''
                        INSERT INTO term_logs (term_id, action, changed_by, new_value, change_time)
                        VALUES (%s, %s, %s, %s, %s)
                    ''', (
                        term_id,
                        'created',
                        'admin',  # Replace with session['username'] or similar if available
                        json.dumps(new_value),
                        get_kampala_time()
                    ))

                    connection.commit()
                    flash("Term successfully added!", "success")

            except Exception as err:
                flash(f"Database error: {err}", "danger")
            finally:
                cursor.close()
                connection.close()

    return render_template('term/add_term.html', study_years=study_years, segment='add_term')
















from flask import request, flash, redirect, url_for, render_template
import json
from datetime import datetime
import pytz

@blueprint.route('/edit_term/<int:term_id>', methods=['GET', 'POST'])
def edit_term(term_id):
    """Handles editing an existing term and logs the changes."""
    
    def get_kampala_time():
        return datetime.now(pytz.timezone("Africa/Kampala"))
    
    def get_current_user():
        # Replace with your actual current user retrieval logic
        return "current_user"

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    if request.method == 'POST':
        term_name = request.form.get('term_name')
        start_on = request.form.get('start_on')
        ends_on = request.form.get('ends_on')
        year_id = request.form.get('year_id')
        status = request.form.get('status')
        print('term:',term_name,'Start:',start_on,'End:',ends_on,'Year: ',year_id,'Status:',status)

        # Validation
        if not term_name or not start_on or not ends_on or not year_id  is None:
            flash("Please fill out all required fields!", "warning")
            return redirect(url_for('term_blueprint.edit_term', term_id=term_id))

        if len(term_name) > 20:
            flash("Term name must be 20 characters or fewer!", "danger")
            return redirect(url_for('term_blueprint.edit_term', term_id=term_id))

        # Fetch old term data for logging
        cursor.execute("SELECT * FROM terms WHERE term_id = %s", (term_id,))
        old_term = cursor.fetchone()

        if not old_term:
            flash("Term not found.", "danger")
            cursor.close()
            connection.close()
            return redirect(url_for('term_blueprint.term'))

        try:
            # Check duplicate term name for a different term in the same year
            cursor.execute("""
                SELECT * FROM terms
                WHERE term_name = %s AND year_id = %s AND term_id != %s
            """, (term_name, year_id, term_id))
            existing_term = cursor.fetchone()
            if existing_term:
                flash("A term with the same name already exists for the selected year!", "warning")
                return redirect(url_for('term_blueprint.edit_term', term_id=term_id))

            # Update term
            cursor.execute("""
                UPDATE terms
                SET term_name = %s, start_on = %s, ends_on = %s, year_id = %s, status = %s
                WHERE term_id = %s
            """, (term_name, start_on, ends_on, year_id, status, term_id))
            connection.commit()

            # Prepare old and new values for logging (as JSON strings)
            old_value = json.dumps(old_term, default=str)
            new_value = json.dumps({
                "term_id": term_id,
                "term_name": term_name,
                "start_on": start_on,
                "ends_on": ends_on,
                "year_id": year_id,
                "status": status
            }, default=str)

            # Insert log entry
            cursor.execute("""
                INSERT INTO term_logs (term_id, action, changed_by, change_time, old_value, new_value, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                term_id,
                "updated",
                get_current_user(),
                get_kampala_time(),
                old_value,
                new_value,
                "Term details updated"
            ))
            connection.commit()

            flash("Term updated successfully!", "success")

        except Exception as e:
            flash(f"An error occurred: {str(e)}", "danger")
        finally:
            cursor.close()
            connection.close()

        return redirect(url_for('term_blueprint.term'))

    else:  # GET request
        cursor.execute("SELECT * FROM terms WHERE term_id = %s", (term_id,))
        term_data = cursor.fetchone()

        if term_data:
            # Optionally fetch study years for dropdown select
            cursor.execute("SELECT year_id, year_name FROM study_year")
            years = cursor.fetchall()
            cursor.close()
            connection.close()

            return render_template('term/edit_term.html', term=term_data, years=years, segment='term')
        else:
            cursor.close()
            connection.close()
            flash("Term not found.", "danger")
            return redirect(url_for('term_blueprint.term'))





















from datetime import datetime
import pytz
import json

def get_kampala_time():
    return datetime.now(pytz.timezone("Africa/Kampala"))

@blueprint.route('/delete_term/<int:term_id>')
def delete_term(term_id):
    """Deletes a term and logs the action."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)  # Use dictionary=True to fetch as dict

    try:
        # Check if term exists
        cursor.execute("SELECT * FROM terms WHERE term_id = %s", (term_id,))
        term = cursor.fetchone()

        if not term:
            flash("Term not found.", "warning")
            return redirect(url_for('term_blueprint.term'))

        # Save old value for logging
        old_value_json = json.dumps(term, default=str)

        # Delete the term
        cursor.execute("DELETE FROM terms WHERE term_id = %s", (term_id,))
        connection.commit()

        # Log the deletion
        cursor.execute("""
            INSERT INTO term_logs (term_id, action, changed_by, change_time, old_value, new_value, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            term_id,
            'deleted',
            'admin_user',  # Replace this with actual logged-in user if available
            get_kampala_time(),
            old_value_json,
            None,
            'Term was deleted from the system.'
        ))
        connection.commit()

        flash("Term deleted successfully.", "success")

    except Exception as e:
        connection.rollback()
        flash(f"An error occurred while deleting the term: {str(e)}", "danger")

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('term_blueprint.term'))










@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("term/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'term'

        return segment

    except:
        return None
