from apps.fixed_assets import blueprint
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

# --- HELPER FUNCTION TO FETCH LOOKUP DATA ---
def fetch_lookup_data(cursor):
    """Fetches locations, suppliers, categories, and users for dropdowns."""
    data = {}
    
    # 1. Locations
    cursor.execute('SELECT LocationID, LocationName FROM locations ORDER BY LocationName')
    data['locations'] = cursor.fetchall()

    # 2. Suppliers
    cursor.execute('SELECT SupplierID, Name FROM Suppliers ORDER BY Name')
    data['suppliers'] = cursor.fetchall()

    # 3. Categories (FIXED: Using 'category_list' instead of 'Categories')
    cursor.execute('SELECT CategoryID, Name FROM category_list ORDER BY Name') 
    data['categories'] = cursor.fetchall()
    
    # 4. Users (for Custodians)
    cursor.execute('SELECT id, first_name, last_name FROM users ORDER BY last_name')
    data['users'] = cursor.fetchall()
    
    return data

# ---

# LIST ASSETS (FIXED ASSETS REGISTER)
@blueprint.route('/assets') 
def assets():
    """Fetches all fixed assets and renders the main register page."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Fetch all assets, including names from linked tables for display
        cursor.execute("""
            SELECT 
                fa.AssetID, fa.IdentificationNumber, fa.AssetDescription, fa.AssetCondition,
                fa.AcquisitionDate, fa.CostValuation, fa.OwnershipStatus,
                loc.LocationName, cat.Name AS CategoryName, 
                sup.Name AS SupplierName, 
                CONCAT(u.first_name, ' ', u.last_name) AS CustodianName
            FROM fixed_assets fa
            JOIN locations loc ON fa.LocationID = loc.LocationID
            JOIN category_list cat ON fa.CategoryID = cat.CategoryID -- FIXED TABLE NAME HERE
            LEFT JOIN Suppliers sup ON fa.SupplierID = sup.SupplierID
            LEFT JOIN users u ON fa.CustodianID = u.id
            ORDER BY fa.IdentificationNumber ASC
        """)
        assets_list = cursor.fetchall()
        
    except Error as e:
        logging.error(f"Database error fetching assets: {e}")
        # Note: If fixed_assets table doesn't exist yet, this will also fail.
        flash("Could not fetch assets due to a database error. Please ensure all tables (fixed_assets, category_list, etc.) exist.", "danger")
        assets_list = []
        
    finally:
        cursor.close()
        connection.close()

    # Renders the template specific to assets
    return render_template('assets/assets.html', assets=assets_list, segment='assets')


# ---

# ADD ASSET (FIXED ASSETS)
@blueprint.route('/add_asset', methods=['GET', 'POST'])
def add_asset():
    """Handles the adding of a new fixed asset."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    lookup_data = fetch_lookup_data(cursor) # Get lookup data for GET/POST failure
    cursor.close()
    connection.close()

    if request.method == 'POST':
        # 1. Capture MANDATORY form data
        id_number = request.form.get('id_number') 
        description = request.form.get('description')
        acquisition_date = request.form.get('acquisition_date')
        cost_valuation = request.form.get('cost_valuation')
        location_id = request.form.get('location_id')
        category_id = request.form.get('category_id') # New mandatory FK
        
        # 2. Capture OPTIONAL/OTHER form data
        serial_number = request.form.get('serial_number')
        supplier_id = request.form.get('supplier_id') or None # Set to None if empty
        custodian_id = request.form.get('custodian_id') or None # Set to None if empty
        ownership_status = request.form.get('ownership_status')
        asset_condition = request.form.get('asset_condition')

        # Simple Mandatory Field Validation
        if not all([id_number, description, acquisition_date, cost_valuation, location_id, category_id]):
            flash("Please fill in all mandatory fields (ID, Description, Date, Cost, Location, Category).", "warning")
            # Re-fetch lookup data before rendering on failure
            connection_fail = get_db_connection()
            cursor_fail = connection_fail.cursor(dictionary=True)
            lookup_data_fail = fetch_lookup_data(cursor_fail)
            cursor_fail.close()
            connection_fail.close()
            return render_template('assets/add_asset.html', **lookup_data_fail, segment='add_asset')

        # Database connection for insertion
        connection = get_db_connection()
        cursor = connection.cursor()

        try:
            # Check if IdentificationNumber already exists
            cursor.execute('SELECT AssetID FROM fixed_assets WHERE IdentificationNumber = %s', (id_number,))
            if cursor.fetchone():
                flash(f"Asset with ID '{id_number}' already exists!", "warning")
                # Re-fetch lookup data before rendering on failure
                connection_fail = get_db_connection()
                cursor_fail = connection_fail.cursor(dictionary=True)
                lookup_data_fail = fetch_lookup_data(cursor_fail)
                cursor_fail.close()
                connection_fail.close()
                return render_template('assets/add_asset.html', **lookup_data_fail, segment='add_asset')

            # Convert cost to Decimal, handle potential errors
            try:
                cost = float(cost_valuation)
            except ValueError:
                flash("Cost Valuation must be a valid number.", "danger")
                # Re-fetch lookup data before rendering on failure
                connection_fail = get_db_connection()
                cursor_fail = connection_fail.cursor(dictionary=True)
                lookup_data_fail = fetch_lookup_data(cursor_fail)
                cursor_fail.close()
                connection_fail.close()
                return render_template('assets/add_asset.html', **lookup_data_fail, segment='add_asset')

            # Insert the new asset into the fixed_assets table
            cursor.execute("""
                INSERT INTO fixed_assets (
                    IdentificationNumber, SerialNumber, AssetDescription, AcquisitionDate, CostValuation, 
                    LocationID, SupplierID, CustodianID, CategoryID, OwnershipStatus, AssetCondition
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                id_number, serial_number, description, acquisition_date, cost, 
                location_id, supplier_id, custodian_id, category_id, ownership_status, asset_condition
            ))
            connection.commit()
            flash(f"Asset '{description}' successfully added!", "success")
            return redirect(url_for('fixed_assets_blueprint.assets')) # Redirect to the main asset list

        except mysql.connector.Error as err:
            logging.error(f"Database Error adding asset: {err}")
            flash(f"Database Error: Could not add asset. {err}", "danger")
            # If database error occurs, return to form with re-fetched lookup data
            connection_fail = get_db_connection()
            cursor_fail = connection_fail.cursor(dictionary=True)
            lookup_data_fail = fetch_lookup_data(cursor_fail)
            cursor_fail.close()
            connection_fail.close()
            return render_template('assets/add_asset.html', **lookup_data_fail, segment='add_asset')

        except Exception as e:
            logging.error(f"Unexpected error adding asset: {e}")
            flash(f"An unexpected error occurred: {e}", "danger")
            # If unexpected error occurs, return to form with re-fetched lookup data
            connection_fail = get_db_connection()
            cursor_fail = connection_fail.cursor(dictionary=True)
            lookup_data_fail = fetch_lookup_data(cursor_fail)
            cursor_fail.close()
            connection_fail.close()
            return render_template('assets/add_asset.html', **lookup_data_fail, segment='add_asset')

        finally:
            cursor.close()
            connection.close()
    
    # GET request
    return render_template('assets/add_asset.html', **lookup_data, segment='add_asset')

# ---

# EDIT ASSET (FIXED ASSETS)
@blueprint.route('/edit_asset/<int:asset_id>', methods=['GET', 'POST'])
def edit_asset(asset_id):
    """Handles editing an existing fixed asset."""
    
    # Use a new connection/cursor for lookup data
    connection_lookup = get_db_connection()
    cursor_lookup = connection_lookup.cursor(dictionary=True)
    lookup_data = fetch_lookup_data(cursor_lookup)
    cursor_lookup.close()
    connection_lookup.close()

    if request.method == 'POST':
        # Capture form data
        id_number = request.form.get('id_number')
        description = request.form.get('description')
        acquisition_date = request.form.get('acquisition_date')
        cost_valuation = request.form.get('cost_valuation')
        location_id = request.form.get('location_id')
        category_id = request.form.get('category_id') 
        serial_number = request.form.get('serial_number')
        supplier_id = request.form.get('supplier_id') or None
        custodian_id = request.form.get('custodian_id') or None
        ownership_status = request.form.get('ownership_status')
        asset_condition = request.form.get('asset_condition')

        # Validation (Simplified for brevity)
        if not all([id_number, description, acquisition_date, cost_valuation, location_id, category_id]):
            flash('Invalid or missing mandatory asset details.', "danger")
            # Need to re-fetch the current asset data to pass back to the template
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM fixed_assets WHERE AssetID = %s", (asset_id,))
            asset = cursor.fetchone()
            cursor.close()
            connection.close()
            return render_template('assets/edit_asset.html', asset=asset, **lookup_data, segment='assets')

        try:
            # Re-establish connection/cursor for update
            connection = get_db_connection()
            cursor = connection.cursor()

            # Update the asset in the fixed_assets table
            cursor.execute("""
                UPDATE fixed_assets
                SET IdentificationNumber = %s, SerialNumber = %s, AssetDescription = %s, 
                    AcquisitionDate = %s, CostValuation = %s, LocationID = %s, 
                    SupplierID = %s, CustodianID = %s, CategoryID = %s,
                    OwnershipStatus = %s, AssetCondition = %s
                WHERE AssetID = %s
            """, (
                id_number, serial_number, description, acquisition_date, cost_valuation, 
                location_id, supplier_id, custodian_id, category_id,
                ownership_status, asset_condition, asset_id
            ))
            connection.commit()

            flash("Asset updated successfully!", "success")
            return redirect(url_for('fixed_assets_blueprint.assets'))

        except mysql.connector.Error as err:
            flash(f"Database Error: Could not update asset. {err}", "danger")
            # Re-fetch the current asset data to pass back to the template on error
            connection_fail = get_db_connection()
            cursor_fail = connection_fail.cursor(dictionary=True)
            cursor_fail.execute("SELECT * FROM fixed_assets WHERE AssetID = %s", (asset_id,))
            asset = cursor_fail.fetchone()
            cursor_fail.close()
            connection_fail.close()
            return render_template('assets/edit_asset.html', asset=asset, **lookup_data, segment='assets')

        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")
            # Re-fetch the current asset data to pass back to the template on error
            connection_fail = get_db_connection()
            cursor_fail = connection_fail.cursor(dictionary=True)
            cursor_fail.execute("SELECT * FROM fixed_assets WHERE AssetID = %s", (asset_id,))
            asset = cursor_fail.fetchone()
            cursor_fail.close()
            connection_fail.close()
            return render_template('assets/edit_asset.html', asset=asset, **lookup_data, segment='assets')

        finally:
            # Ensure connection is closed after final attempt
            if 'connection' in locals() and connection.is_connected():
                 cursor.close()
                 connection.close()


    elif request.method == 'GET':
        # Retrieve the asset to pre-fill the form
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM fixed_assets WHERE AssetID = %s", (asset_id,))
            asset = cursor.fetchone()
        except Error as e:
            logging.error(f"Database error fetching asset {asset_id}: {e}")
            asset = None
        finally:
            cursor.close()
            connection.close()

        if asset:
            # Pass the retrieved asset and lookup data to the template
            return render_template('assets/edit_asset.html', asset=asset, **lookup_data, segment='assets')
        else:
            flash("Asset not found.", "danger")
            return redirect(url_for('fixed_assets_blueprint.assets'))

# ---

# DELETE ASSET (FIXED ASSETS)
@blueprint.route('/delete_asset/<int:asset_id>')
def delete_asset(asset_id):
    """Deletes a fixed asset from the database."""
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Get asset description for flash message before deleting
        cursor.execute('SELECT AssetDescription FROM fixed_assets WHERE AssetID = %s', (asset_id,))
        asset_info = cursor.fetchone()
        asset_description = asset_info[0] if asset_info else "the asset"
        
        # Delete the asset
        cursor.execute('DELETE FROM fixed_assets WHERE AssetID = %s', (asset_id,))
        connection.commit()
        flash(f"Asset '{asset_description}' deleted successfully.", "success")
        
    except Exception as e:
        # Handle Foreign Key errors if the asset is linked to other audit/disposal logs
        flash(f"Error: Cannot delete asset. It may be linked to audit history or other records. ({str(e)})", "danger")
    finally:
        cursor.close()
        connection.close()

    # Redirect to the assets list
    return redirect(url_for('fixed_assets_blueprint.assets'))
