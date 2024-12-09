import flask
from flask import Flask, render_template, session, jsonify, request, make_response, redirect, url_for
import DatabaseClient
import pandas as pd
import numpy as np
import json
from urllib.parse import unquote
import dotenv
import auth
import os
from top import app
import cloudinary
from cloudinary.uploader import upload
from cloudinary.utils import cloudinary_url
import re
from flask_paginate import Pagination, get_page_parameter

db = DatabaseClient.DatabaseClient()

dotenv.load_dotenv()
app.secret_key = os.environ['APP_SECRET_KEY']

cloudinary.config( 
    cloud_name = os.environ['CLOUDINARY_CLOUD_NAME'], 
    api_key = os.environ['CLOUDINARY_API_KEY'], 
    api_secret = os.environ['CLOUDINARY_API_SECRET'], 
    secure=True
)

@app.route('/', methods=['GET'])
@app.route('/?', methods=['GET'])
@app.route('/index', methods=['GET'])
def index():
    #username = auth.authenticate()
    #db.insert_user(emailId=username, password='')
    return render_template('landing_page.html')

@app.route('/welcome_page', methods=['GET', 'POST'])
def welcome_page():
    username = auth.authenticate()
    db.insert_user(emailId=username, password='')
    # if 'username' not in session:
    #     session['username'] = auth.authenticate()
    # username = session['username']
    name = session['name']
    return render_template('welcome_page.html', username=username, name=name)

@app.route('/pantry', methods=['GET'])
def pantry_page():
    username = auth.authenticate()
    ingredients = pd.read_csv('webscraping/output/ingredients_list.csv')
    ingredients = ingredients.values.tolist()
    # ingredients = db.get_pantry_ingredients()
    ingredients = np.squeeze(ingredients)
    pantry_items = db.get_user_inventory(username)
    return render_template('prototype_pantry.html', ingredients=ingredients, pantry_items = pantry_items, username=username)

@app.route('/pantry/save', methods=['POST'])
def save_pantry_items():
    username = auth.authenticate()
    data = request.get_json()
    pantry_items = data.get('pantry_items', [])
    db.update_user_inventory(username, pantry_items)
    return jsonify({'success': True})

@app.route('/recommended_recipes', methods=['GET'])
def results_page():
    username = auth.authenticate()
    pantry_items = db.get_user_inventory(username)
    pantry_items.append("salt")
    pantry_items.append("sea salt")
    pantry_items.append("rock salt")
    pantry_items.append("black pepper")
    pantry_items = [ingredient.lower() for ingredient in pantry_items]
    clear = flask.request.args.get('clear', type=str)
    skill = flask.request.args.get('skill', type = str)
    max_time = flask.request.args.get('time', type = str)
    if clear == 'True':
        skill = None
        max_time = None
    else:
        if not skill: skill = flask.request.cookies.get('prev_skill')
        if not max_time: max_time = flask.request.cookies.get('prev_max_time')
    if max_time:
        try:
            max_time = int(max_time)
        except ValueError:
            skill = max_time = None
            return render_template('validparam.html', redirect='recommended')
    else:
        max_time = None
    
    if skill: 
        if skill not in ['Beginner', 'Intermediate', 'Advanced']:
            skill = max_time = None
            return render_template('validparam.html', redirect='recommended')

    user_data = db.get_user(username)
    restrictions = user_data['restrictions']
    recipes = db.return_page_recipes_rec(pantry_items, skill=skill, max_time=max_time, restrictions=restrictions)

    # add paging
    per_page = 20
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1
    offset = (page-1)*per_page
    rpart = recipes[offset:offset+per_page]
    pagination = Pagination(page=page,per_page=per_page, offset=offset, total=len(recipes), record_name='recipes')

    resp = make_response(render_template('prototype_recommended_recipes.html', recipes=recipes, rpart=rpart, username=username, recommended=True, 
                                         user_data=user_data, pagination=pagination, pantry_items = pantry_items, restrictions=restrictions,
                                         prev_skill=skill, prev_max_time=max_time))
    if skill: resp.set_cookie('prev_skill', skill)
    else: resp.delete_cookie('prev_skill')
    if max_time: resp.set_cookie('prev_max_time', str(max_time))
    else: resp.delete_cookie('prev_max_time')
    return resp

@app.route('/all_recipes', methods=['GET', 'POST'])
def all_recipes():
    username = auth.authenticate()
    user_data = db.get_user(username)
    restrictions = user_data['restrictions']
    if restrictions is None:
        restrictions = []
    clear = flask.request.args.get('clear', type=str)
    query = flask.request.args.get('search', type = str)
    skill = flask.request.args.get('skill', type = str)
    max_time = flask.request.args.get('time', type = str)
    if clear == 'True':
        query = None
        skill = None
        max_time = None
    else:
        if not query: query = flask.request.cookies.get('prev_query')
        if not skill: skill = flask.request.cookies.get('prev_skill')
        if not max_time: max_time = flask.request.cookies.get('prev_max_time')
    if max_time:
        try:
            max_time = int(max_time)
        except ValueError:
            query = skill = max_time = None
            return render_template('validparam.html', redirect='all_recipes')
    else:
        max_time = None
    
    if skill: 
        if skill not in ['Beginner', 'Intermediate', 'Advanced']:
            query = skill = max_time = None
            return render_template('validparam.html', redirect='all_recipes')

    recipes, indicator = db.filter_recipes(skill=skill, max_time=max_time, restrictions=restrictions, search=query)
    extended_results = False
    if indicator == 1:
        extended_results = True
    
    # print(recipes)
    # add paging

    per_page = 20
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1
    offset = (page-1)*per_page
    rpart = recipes[offset:offset+per_page]
    pagination = Pagination(page=page,per_page=per_page, offset=offset, total=len(recipes), record_name='recipes')

    resp = make_response(render_template('prototype_recommended_recipes.html', recipes=recipes, rpart=rpart, username=username, recommended=False, 
                           user_data=user_data, pagination=pagination, restrictions=restrictions, query=query,
                           prev_skill=skill, prev_max_time=max_time, extended_results=extended_results))
    if skill: resp.set_cookie('prev_skill', skill)
    else: resp.delete_cookie('prev_skill')
    if max_time: resp.set_cookie('prev_max_time', str(max_time))
    else: resp.delete_cookie('prev_max_time')
    if query: resp.set_cookie('prev_query', query)
    else: resp.delete_cookie('prev_query')
    return resp


@app.route('/recipe_page', methods=['GET'])
def recipe_page():
    username = auth.authenticate()
    recipe_id = flask.request.args.get("recipe")
    
    recipe = db.return_recipe(recipe_id)

    if recipe is None:
        return render_template('error.html')
    
    return render_template('prototype_recipe_page.html', recipe=recipe, username=username)

@app.route('/wishlist', methods=['GET', 'POST'])
def wishlist():
    if 'username' not in session:
        session['username'] = auth.authenticate()
    username = session['username']
    
    wishList = db.get_user_wishlist(username)
    recipe_id = flask.request.form.get('recipe_id')

    already_in_wishlist = False
    if recipe_id in wishList:
        already_in_wishlist = True
    else:
        wishList.append(recipe_id)
        db.update_user_wishlist(username, wishList)
    
    full_wishList = []
    for r_id in wishList:
        recipe = db.return_recipe(r_id)
        if recipe:  
            full_wishList.append(recipe)
    
    return render_template('wishlist.html', wishList=full_wishList, username=username, already_in_wishlist=already_in_wishlist)


@app.route('/remove_from_wishlist', methods=['POST'])
def remove_from_wishlist():
    if 'username' not in session:
        session['username'] = auth.authenticate()
    username = session['username']
    
    wishList = db.get_user_wishlist(username)
    
    recipe_id = flask.request.form.get('recipe_id')

    if recipe_id in wishList:
        wishList.remove(recipe_id)
        db.update_user_wishlist(username, wishList)

    full_wishList = []
    for r_id in wishList:
        recipe = db.return_recipe(r_id)
        if recipe:
            full_wishList.append(recipe)

    return redirect(url_for('wishlist'))

@app.route('/groceries', methods=['GET'])
def groceries_display():
    username = auth.authenticate()
    groceryList = session['groceryList']
    return render_template('grocery_list.html', groceryList=groceryList, username=username)

@app.route('/add_to_groceries', methods=['POST']) 
def add_to_groceries():
    groceries = flask.request.form['groceries']
    
    #print("GROCERIES", groceries)
    groceries = groceries.replace("\'", "\"")
    ing_list = json.loads(groceries)

    if 'username' not in session:
        session['username'] = auth.authenticate()
    username = session['username']
    if 'groceryList' not in session:
        session['groceryList'] = db.get_user_grocerylist(username)
    groceryList = session['groceryList']

    for ingredient in ing_list:
        if ingredient not in groceryList:
            groceryList.append(ingredient)
    db.update_user_grocerylist(username, groceryList)
    session['groceryList'] = groceryList
    
    return render_template('grocery_list.html', groceryList=groceryList, username=username)

# update grocery list in session
@app.route('/remove_from_groceries', methods=['POST'])
def remove_from_groceries():
    if 'username' not in session:
        session['username'] = auth.authenticate()
    username = session['username']
    
    item = request.get_json()
    if 'groceryList' not in session:
        session['groceryList'] = db.get_user_grocerylist(username)
    groceryList = session['groceryList']

    if item in groceryList:
        groceryList.remove(item)
    db.update_user_grocerylist(username, groceryList)
    session['groceryList'] = groceryList
    

@app.route('/profile_page', methods=['GET', 'POST'])
def profile_page():
    username = auth.authenticate()
    upload_result = None
    error = ""

    if request.method == 'POST':
        if 'file' in request.files:  
            file_to_upload = request.files['file']
            try: 
                upload_result = upload(file_to_upload)
                url, options = cloudinary_url(upload_result['public_id'], format='jpg', crop='fill', width=100, height=100)
                db.update_user_pic(username, url)
            except Exception as ex: 
                error = ex
           
        else: 
            updated_restrictions = request.form.getlist('restriction')
            db.delete_user_restrictions(username)
            db.update_user_restrictions(username, updated_restrictions)

    user_data = db.get_user(username)
    return render_template('profile_page.html', user_data=user_data, error=error)

@app.route('/completed', methods=['GET', 'POST'])
def completed():
    if 'username' not in session:
        session['username'] = auth.authenticate()
    username = session['username']
    
    completed = db.get_user_completed(username)
    recipe_id = flask.request.form.get('recipe_id')

    if recipe_id not in completed:
        completed.append(recipe_id)
        # print(completed)
        print(db.update_user_completed(username, completed))

    # print(db.get_user_completed(username))
    # for i, x in enumerate(completed):
    #     print(i, ": ", x)  # PRINT HERE

    full_completed = []
    for r_id in completed:
        recipe = db.return_recipe(r_id)
    
        if recipe:
            # print(recipe)  # PRINT HERE
            full_completed.append(recipe)

    reviews = db.get_user_reviews(username)

    return render_template('prototype_finished_recipes.html', completed=full_completed, username=username, reviews=reviews)

@app.route('/favorites', methods=['GET', 'POST'])
def favorites():
    if 'username' not in session:
        session['username'] = auth.authenticate()
    username = session['username']
    favRecipes = db.get_user_favRecipes(username)
    
    # Only try to get recipe_id and update favorites if it's a POST request
    if flask.request.method == 'POST':
        recipe_id = flask.request.form.get('recipe_id')
        if recipe_id and recipe_id not in favRecipes:
            favRecipes.append(recipe_id)
            db.update_user_favRecipes(username, favRecipes)
            session['favRecipes'] = favRecipes
            
    # recipe_id = flask.request.form.get('recipe_id')

    # if recipe_id not in favRecipes:
    #     favRecipes.append(recipe_id)
    #     db.update_user_favRecipes(username, favRecipes)
    #     session['favRecipes'] = favRecipes
        
    
    full_favRecipes = []
    for r_id in favRecipes:
        recipe = db.return_recipe(r_id)
        if recipe:
            full_favRecipes.append(recipe)

    return render_template('prototype_favorite_recipes.html', favRecipes=full_favRecipes, username=username)

@app.route('/remove_from_favorites', methods=['POST'])
def remove_from_favorites():
    if 'username' not in session:
        session['username'] = auth.authenticate()
    username = session['username']
    
    favRecipes = db.get_user_favRecipes(username)
    
    recipe_id = flask.request.form.get('recipe_id')

    if recipe_id in favRecipes:
        favRecipes.remove(recipe_id)
        db.update_user_favRecipes(username, favRecipes)

    full_favRecipes = []
    for r_id in favRecipes:
        recipe = db.return_recipe(r_id)
        if recipe:
            full_favRecipes.append(recipe)

    return render_template('prototype_favorite_recipes.html', favRecipes=full_favRecipes, username=username)

@app.route('/add_review', methods=['POST'])
def add_review():
    if 'username' not in session:
        session['username'] = auth.authenticate()
    username = session['username']

    recipe_id = flask.request.form.get('recipe_id')
    review = flask.request.form.get('review')

    reviews = db.get_user_reviews(username)
    reviews[recipe_id] = review
    db.update_user_reviews(username, reviews)

    
    full_completed = db.get_user_completed(username)
    return render_template('prototype_finished_recipes.html', completed=full_completed, username=username, reviews=reviews)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html'), 404

@app.errorhandler(500)
def internal_error(e):
    return render_template('internal_error.html'), 500

    



    