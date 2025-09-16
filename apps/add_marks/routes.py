from apps.add_marks import blueprint
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
import numpy as np 
from datetime import datetime
import pytz
from flask import request, session, flash, redirect, url_for




def get_kampala_time():
    kampala = pytz.timezone("Africa/Kampala")
    return datetime.now(kampala)



from mysql.connector import Error

@blueprint.route('/add_marks', methods=['GET', 'POST'])
def add_marks():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Load dropdown values
    cursor.execute("SELECT * FROM classes")
    class_list = cursor.fetchall()
    cursor.execute("SELECT * FROM study_year")
    study_years = cursor.fetchall()
    cursor.execute("SELECT * FROM terms")
    terms = cursor.fetchall()
    cursor.execute("SELECT * FROM assessment")
    assessments = cursor.fetchall()
    cursor.execute("SELECT * FROM subjects")
    subjects = cursor.fetchall()
    cursor.execute("SELECT * FROM stream")
    streams = cursor.fetchall()
    cursor.execute("SELECT * FROM pupils")
    pupils = cursor.fetchall()

    # --- NO DATA INSERTION LOGIC HERE ---

    # Get filter parameters from query string
    class_id = request.args.get('class_id', type=int)
    year_id = request.args.get('year_id', type=int)
    term_id = request.args.get('term_id', type=int)
    subject_id = request.args.get('subject_id', type=int)
    assessment_name = request.args.get('assessment_name', type=str)
    stream_id = request.args.get('stream_id', type=int)
    pupil_name = request.args.get('pupil_name', type=str)
    reg_no = request.args.get('reg_no', type=str)

    # If required filters are missing, render the page with empty results
    if not (year_id and term_id and subject_id and assessment_name):
        cursor.close()
        connection.close()
        return render_template('add_marks/add_marks.html',
            add_marks=[], class_list=class_list, study_years=study_years,
            terms=terms, subjects=subjects, assessments=assessments,
            streams=streams, pupils=pupils,
            selected_class_id=class_id,
            selected_study_year_id=year_id,
            selected_term_id=term_id,
            selected_assessment_name=assessment_name,
            selected_subject_id=subject_id,
            selected_stream_id=stream_id,
            selected_pupil_name=pupil_name,
            entered_reg_no=reg_no,
            segment='add_marks'
        )

    # Query: Pupils without an existing score for the specified combo
    query = """
        SELECT 
            p.reg_no,
            CONCAT_WS(' ', p.last_name, p.first_name, p.other_name) AS full_name,
            p.pupil_id,
            y.year_name,
            t.term_name,
            str.stream_name,
            sub.subject_name,
            a.assessment_name,
            p.class_id,
            p.stream_id,
            %s AS year_id,
            %s AS term_id,
            (SELECT assessment_id FROM assessment WHERE assessment_name = %s LIMIT 1) AS assessment_id,
            %s AS subject_id
        FROM pupils p
        LEFT JOIN stream str ON p.stream_id = str.stream_id
        LEFT JOIN study_year y ON y.year_id = %s
        LEFT JOIN terms t ON t.term_id = %s
        LEFT JOIN subjects sub ON sub.subject_id = %s
        LEFT JOIN assessment a ON a.assessment_name = %s
        WHERE NOT EXISTS (
            SELECT 1 FROM scores s
            WHERE s.reg_no = p.reg_no
              AND s.year_id = %s
              AND s.term_id = %s
              AND s.subject_id = %s
              AND s.assessment_id = (SELECT assessment_id FROM assessment WHERE assessment_name = %s LIMIT 1)
        )
    """

    query_params = [
        year_id, term_id, assessment_name, subject_id,  # select fields
        year_id, term_id, subject_id, assessment_name,  # joins
        year_id, term_id, subject_id, assessment_name   # subquery filters
    ]

    # Optional filters
    if class_id:
        query += " AND p.class_id = %s"
        query_params.append(class_id)
    if stream_id:
        query += " AND p.stream_id = %s"
        query_params.append(stream_id)
    if pupil_name:
        query += " AND TRIM(CONCAT(p.first_name, ' ', COALESCE(p.other_name, ''), ' ', p.last_name)) LIKE %s"
        query_params.append(f"%{pupil_name}%")
    if reg_no:
        query += " AND p.reg_no = %s"
        query_params.append(reg_no)

    query += " ORDER BY p.last_name, p.first_name, p.other_name"

    cursor.execute(query, query_params)
    add_marks = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template('add_marks/add_marks.html',
        add_marks=add_marks,
        class_list=class_list,
        study_years=study_years,
        terms=terms,
        subjects=subjects,
        assessments=assessments,
        streams=streams,
        pupils=pupils,
        selected_class_id=class_id,
        selected_study_year_id=year_id,
        selected_term_id=term_id,
        selected_assessment_name=assessment_name,
        selected_subject_id=subject_id,
        selected_stream_id=stream_id,
        selected_pupil_name=pupil_name,
        entered_reg_no=reg_no,
        segment='add_marks'
    )










@blueprint.route('/teacher_add_marks', methods=['GET', 'POST'])
def teacher_add_marks():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    user_id = session.get('id')  # Get logged-in teacher ID
    if not user_id:
        flash('You must be logged in as a teacher to access this page.', 'danger')
        return redirect(url_for('authentication_blueprint.login'))

    # Load dropdowns based on assignments only
    # Classes (still unfiltered unless needed)
    cursor.execute("""
        SELECT DISTINCT c.class_id, c.class_name
    FROM classes c
    JOIN stream s ON s.class_id = c.class_id
    JOIN subject_assignment sa ON sa.stream_id = s.stream_id
    WHERE sa.user_id = %s
    """, (user_id,))
    class_list = cursor.fetchall()



    # Study years assigned to this teacher
    cursor.execute("""
        SELECT DISTINCT y.year_id, y.year_name
        FROM study_year y
        JOIN subject_assignment sa ON sa.year_id = y.year_id
        WHERE sa.user_id = %s
    """, (user_id,))
    study_years = cursor.fetchall()

    # Terms (likely fixed for all, can be filtered similarly if needed)
    cursor.execute("SELECT * FROM terms")
    terms = cursor.fetchall()

    # Assessments (assumed to be global, keep all)
    cursor.execute("SELECT * FROM assessment")
    assessments = cursor.fetchall()

    # Subjects assigned to this teacher
    cursor.execute("""
        SELECT DISTINCT s.subject_id, s.subject_name
        FROM subjects s
        JOIN subject_assignment sa ON sa.subject_id = s.subject_id
        WHERE sa.user_id = %s
    """, (user_id,))
    subjects = cursor.fetchall()

    # Streams assigned to this teacher
    cursor.execute("""
        SELECT DISTINCT str.stream_id, str.stream_name
        FROM stream str
        JOIN subject_assignment sa ON sa.stream_id = str.stream_id
        WHERE sa.user_id = %s
    """, (user_id,))
    streams = cursor.fetchall()

    cursor.execute("""
    SELECT DISTINCT p.*
    FROM pupils p
    JOIN subject_assignment sa 
        ON p.stream_id = sa.stream_id
       AND sa.year_id = p.year_id
    WHERE sa.user_id = %s
    """, (user_id,))
    pupils = cursor.fetchall()


    # Filter parameters
    class_id = request.args.get('class_id', type=int)
    year_id = request.args.get('year_id', type=int)
    term_id = request.args.get('term_id', type=int)
    subject_id = request.args.get('subject_id', type=int)
    assessment_name = request.args.get('assessment_name', type=str)
    stream_id = request.args.get('stream_id', type=int)
    pupil_name = request.args.get('pupil_name', type=str)
    reg_no = request.args.get('reg_no', type=str)

    if not (year_id and term_id and subject_id and assessment_name):
        cursor.close()
        connection.close()
        return render_template('add_marks/teacher_add_marks.html',
            add_marks=[], class_list=class_list, study_years=study_years,
            terms=terms, subjects=subjects, assessments=assessments,
            streams=streams, pupils=pupils,
            selected_class_id=class_id,
            selected_study_year_id=year_id,
            selected_term_id=term_id,
            selected_assessment_name=assessment_name,
            selected_subject_id=subject_id,
            selected_stream_id=stream_id,
            selected_pupil_name=pupil_name,
            entered_reg_no=reg_no,
            segment='add_marks'
        )

    query = """
        SELECT 
            p.reg_no,
            CONCAT_WS(' ', p.last_name, p.first_name, p.other_name) AS full_name,
            p.pupil_id,
            y.year_name,
            t.term_name,
            str.stream_name,
            sub.subject_name,
            a.assessment_name,
            p.class_id,
            p.stream_id,
            %s AS year_id,
            %s AS term_id,
            (SELECT assessment_id FROM assessment WHERE assessment_name = %s LIMIT 1) AS assessment_id,
            %s AS subject_id
        FROM pupils p
        INNER JOIN subject_assignment sa ON sa.stream_id = p.stream_id 
            AND sa.subject_id = %s
            AND sa.year_id = %s
            AND sa.user_id = %s
        LEFT JOIN stream str ON p.stream_id = str.stream_id
        LEFT JOIN study_year y ON y.year_id = %s
        LEFT JOIN terms t ON t.term_id = %s
        LEFT JOIN subjects sub ON sub.subject_id = %s
        LEFT JOIN assessment a ON a.assessment_name = %s
        WHERE NOT EXISTS (
            SELECT 1 FROM scores s
            WHERE s.reg_no = p.reg_no
              AND s.year_id = %s
              AND s.term_id = %s
              AND s.subject_id = %s
              AND s.assessment_id = (SELECT assessment_id FROM assessment WHERE assessment_name = %s LIMIT 1)
        )
    """

    query_params = [
        year_id, term_id, assessment_name, subject_id,  # SELECT fields
        subject_id, year_id, user_id,                   # subject_assignment join
        year_id, term_id, subject_id, assessment_name,  # LEFT JOINs
        year_id, term_id, subject_id, assessment_name   # Subquery for scores
    ]

    if class_id:
        query += " AND p.class_id = %s"
        query_params.append(class_id)
    if stream_id:
        query += " AND p.stream_id = %s"
        query_params.append(stream_id)
    if pupil_name:
        query += " AND TRIM(CONCAT(p.first_name, ' ', COALESCE(p.other_name, ''), ' ', p.last_name)) LIKE %s"
        query_params.append(f"%{pupil_name}%")
    if reg_no:
        query += " AND p.reg_no = %s"
        query_params.append(reg_no)

    query += " ORDER BY p.last_name, p.first_name, p.other_name"

    cursor.execute(query, query_params)
    add_marks = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template('add_marks/teacher_add_marks.html',
        add_marks=add_marks,
        class_list=class_list,
        study_years=study_years,
        terms=terms,
        subjects=subjects,
        assessments=assessments,
        streams=streams,
        pupils=pupils,
        selected_class_id=class_id,
        selected_study_year_id=year_id,
        selected_term_id=term_id,
        selected_assessment_name=assessment_name,
        selected_subject_id=subject_id,
        selected_stream_id=stream_id,
        selected_pupil_name=pupil_name,
        entered_reg_no=reg_no,
        segment='add_marks'
    )











@blueprint.route('/action_add_marks', methods=['POST'])
def action_add_marks():
    """Handles adding marks and logging them."""

    user_id = session.get('id')
    if not user_id:
        flash("You must be logged in to add marks.", "danger")
        return redirect(url_for('authentication_blueprint.login'))

    form_data = request.form.to_dict(flat=False)
    submitted_pupil_id = request.form.get('submit_add')  # For individual submissions

    # Step 1: Parse submitted marks and remarks
    add_marks = {}
    add_remarks = {}

    for key, values in form_data.items():
        if key.startswith("add_marks[") and key.endswith("]"):
            pupil_id = key[10:-1]
            if not submitted_pupil_id or pupil_id == submitted_pupil_id:
                add_marks[pupil_id] = values[0]

        if key.startswith("add_remarks[") and key.endswith("]"):
            pupil_id = key[12:-1]
            if not submitted_pupil_id or pupil_id == submitted_pupil_id:
                add_remarks[pupil_id] = values[0]

    if not add_marks:
        flash("No marks submitted.", "warning")
        return redirect(request.referrer or url_for('reports_blueprint.reports'))

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        success_count = 0
        errors = []

        for pupil_id, mark_str in add_marks.items():
            try:
                mark = float(mark_str)
                if mark < 0 or mark > 100:
                    errors.append(f"Invalid mark {mark} for pupil ID {pupil_id}. Skipped.")
                    continue
            except ValueError:
                errors.append(f"Invalid mark input for pupil ID {pupil_id}. Skipped.")
                continue

            remark = add_remarks.get(pupil_id, '')

            # Fetch other fields from hidden inputs
            def get_field(field): return request.form.get(f"{field}[{pupil_id}]")

            reg_no = get_field("reg_no")
            class_id = get_field("class_id")
            stream_id = get_field("stream_id")
            term_id = get_field("term_id")
            year_id = get_field("year_id")
            assessment_id = get_field("assessment_id")
            subject_id = get_field("subject_id")

            # Check required fields
            missing = [f for f in ['reg_no', 'class_id', 'stream_id', 'term_id', 'year_id', 'assessment_id', 'subject_id']
                       if not locals()[f]]
            if missing:
                errors.append(f"Missing fields {missing} for pupil ID {pupil_id}. Skipped.")
                continue

            kampala_time = get_kampala_time()

            # Insert into `scores` table
            cursor.execute("""
                INSERT INTO scores
                (user_id, reg_no, class_id, stream_id, term_id, year_id,
                 assessment_id, subject_id, Mark, notes, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                user_id, reg_no, int(class_id), int(stream_id), int(term_id),
                int(year_id), int(assessment_id), int(subject_id),
                mark, remark, kampala_time, kampala_time
            ))

            new_score_id = cursor.lastrowid

            # Insert into `add_score_logs`
            cursor.execute("""
                INSERT INTO add_score_logs
                (score_id, user_id, reg_no, class_id, stream_id, term_id,
                 year_id, assessment_id, subject_id, new_mark, notes, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                new_score_id, user_id, reg_no, int(class_id), int(stream_id),
                int(term_id), int(year_id), int(assessment_id), int(subject_id),
                mark, remark, kampala_time
            ))

            success_count += 1

        connection.commit()

        if success_count:
            flash(f"Successfully added {success_count} score(s).", "success")
        if errors:
            flash("Some issues occurred:<br>" + "<br>".join(errors), "warning")

    except Exception as e:
        connection.rollback()
        flash(f"An error occurred while saving: {str(e)}", "danger")

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return redirect(request.referrer or url_for('reports_blueprint.reports'))




