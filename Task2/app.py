from collections import Counter
from flask import Flask, jsonify, request
from pydantic.experimental import pipeline
from pymongo import MongoClient
from flask_cors import CORS
from datetime import datetime, timedelta, timezone
from bson import ObjectId
from textblob import TextBlob


def serialize_doc(doc):
    """Convert MongoDB document fields to JSON serializable format."""
    if isinstance(doc, dict):
        return {k: serialize_doc(v) for k, v in doc.items()}
    elif isinstance(doc, list):
        return [serialize_doc(elem) for elem in doc]
    elif isinstance(doc, ObjectId):
        return str(doc)
    else:
        return doc

def serialize_objectid(data):
    if isinstance(data, dict):
        return {k: serialize_objectid(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [serialize_objectid(i) for i in data]
    elif isinstance(data, ObjectId):
        return str(data)
    return data

def arrange_objectid(data):
    if isinstance(data, list):
        return [arrange_objectid(item) for item in data]
    elif isinstance(data, dict):
        return {key: arrange_objectid(value) for key, value in data.items()}
    elif isinstance(data, ObjectId):
        return str(data) # Convert ObjectId to string
    else:
        return data

def arrange_objectid(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")



# Helper function to convert ObjectId to string
def convert_objectid_to_str(data):
    if isinstance(data, list):
        for item in data:
            if '_id' in item:
                item['_id'] = str(item['_id'])
    elif isinstance(data, dict):
        if '_id' in data:
            data['_id'] = str(data['_id'])
    return data

def serialize_doc(doc):
    """Convert MongoDB document fields to JSON serializable format."""
    if isinstance(doc, dict):
        return {k: serialize_doc(v) for k, v in doc.items()}
    elif isinstance(doc, list):
        return [serialize_doc(elem) for elem in doc]
    elif isinstance(doc, ObjectId):
        return str(doc)
    else:
        return doc


app = Flask(__name__)
CORS(app)

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["almayadeen"]
collection = db["articles_clean"]




@app.route('/top_keywords', methods=['GET'])
def top_keywords():
    pipeline = [
        {"$unwind": "$keywords"},
        {"$group": {"_id": "$keywords", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    result = list(collection.aggregate(pipeline))
    return jsonify(result)

@app.route('/top_authors', methods=['GET'])
def top_authors():
    pipeline = [
        {"$group": {"_id": "$author", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    result = list(collection.aggregate(pipeline))
    return jsonify(result)


@app.route('/articles_by_date', methods=['GET'])
def articles_by_date():
    """Retrieve articles grouped by date."""
    pipeline = [
        {"$addFields": {
            "published_time_date": {
                "$dateFromString": {
                    "dateString": "$published_time",
                    "format": "%Y-%m-%dT%H:%M:%S%z" # Correct format for timezone
                }
            }
        }},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$published_time_date"}},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]

    import pymongo
    try:
        result = list(collection.aggregate(pipeline))
        print("Aggregation result:", result) # Debugging output
        if not result:
            print("No documents matched the query.")
        return jsonify(result)
    except pymongo.errors.OperationFailure as e:
        print(f"Aggregation error: {e}")
        return jsonify({"error": "Aggregation failed"}), 500

@app.route('/articles_by_word_count', methods=['GET'])
def articles_by_word_count():
    pipeline = [
        {
            "$project": {
                "word_count": {
                    "$cond": {
                        "if": {"$and": [{"$ne": ["$full_text", None]}, {"$eq": [{"$type": "$full_text"}, "string"]}]},
                        "then": {"$strLenCP": "$full_text"},
                        "else": 0 # Fallback value for missing or non-string `full_text`
                    }
                }
            }
        },
        {"$group": {"_id": "$word_count", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]
    result = list(collection.aggregate(pipeline))
    return jsonify(result)

@app.route('/articles_by_language', methods=['GET'])
def articles_by_language():
    if collection is None:
        return "MongoDB connection error.", 500

    try:
        # Pipeline to group articles by language and count the number of articles for each language
        pipeline = [
            {"$match": {"lang": {"$exists": True}}}, # Ensure the lang field exists
            {"$group": {
                "_id": "$lang", # Group by the lang field
                "count": {"$sum": 1} # Count the number of articles per language
            }},
            {"$sort": {"count": -1}} # Sort by count in descending order
        ]

        # Execute the aggregation pipeline
        result = list(collection.aggregate(pipeline))

        # Format the result
        formatted_result = []
        for article in result:
            lang_code = article['_id']
            count = article['count']
            # Convert lang_code to a more readable format if necessary
            if lang_code == "ar":
                language = "Arabic"
            elif lang_code == "en":
                language = "English"
            else:
                language = "Unknown" # For any other language codes
            formatted_result.append(f"{language} ({count} articles)")

        # Return the list of articles by language
        return jsonify(formatted_result)

    except Exception as e:
        return f"An error occurred while fetching articles by language: {e}", 500



@app.route('/articles_by_classes', methods=['GET'])
def articles_by_classes():
    pipeline = [
        {"$unwind": "$classes"},
        {"$group": {"_id": "$classes", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    result = list(collection.aggregate(pipeline))
    return jsonify(result)


@app.route('/recent_articles', methods=['GET'])
def recent_articles():
    pipeline = [
        {"$sort": {"published_date": -1}},
        {"$limit": 10}
    ]
    result = list(collection.aggregate(pipeline))

    # Convert ObjectId to string
    for article in result:
        article["_id"] = str(article["_id"])

    return jsonify(result)


@app.route('/articles_by_keyword/<keyword>', methods=['GET'])
def articles_by_keyword(keyword):
    pipeline = [
        {"$match": {"keywords": keyword}}, # Match articles with the specified keyword
        {"$sort": {"publication_date": -1}}, # Sort articles by publication_date in descending order
        {"$limit": 10} # Limit the number of articles returned
    ]
    result = list(collection.aggregate(pipeline))

    # Convert ObjectId to string
    for article in result:
        article["_id"] = str(article["_id"])

    return jsonify(result)



@app.route('/articles_by_author/<author_name>', methods=['GET'])
def articles_by_author(author_name):
    try:
        # Perform a case-insensitive search in the 'author' field
        articles = collection.find({
            'author': {'$regex': f'^{author_name}$', '$options': 'i'}
        })

        # Collect the titles of the articles written by the specified author
        result = [article.get('title', 'No Title') for article in articles]

        # Count the number of articles
        article_count = len(result)

        # Return the count
        return jsonify({"author": author_name, "count": article_count})

    except Exception as e:
        # Print the exception and return a 500 status code with error message
        print(f"An error occurred: {e}")
        return jsonify({"error": "An error occurred while fetching articles."}), 500


@app.route('/top_classes', methods=['GET'])
def top_classes():
    pipeline = [
        {"$unwind": "$classes"},
        {"$group": {"_id": "$classes", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    result = list(collection.aggregate(pipeline))
    return jsonify(result)

# @app.route('/article_details/<postid>', methods=['GET'])
# def article_details(postid):
# if collection is None:
# return jsonify({"error": "MongoDB connection error."}), 500

# try:
# # Debug: Print the postid being queried
# print(f"Querying for postid: {postid}")

# # Find the article by postid
# article = collection.find_one({'postid': postid})

# # Debug: Print the result of the query
# if article is None:
# print("No article found.")
# return jsonify({"error": "Article not found."}), 404

# print(f"Article found: {article}")

# # Extract relevant details
# details = {
# "URL": article.get('url', 'No URL'),
# "Title": article.get('title', 'No Title'),
# "Keywords": article.get('keywords', [])
# }

# return jsonify(details)

# except Exception as e:
# # Print the exception and return a 500 status code with error message
# print(f"An error occurred: {e}")
# return jsonify({"error": f"An error occurred while fetching article details: {e}"}), 500



@app.route('/article_details', methods=['GET'])
def multiple_article_details():
    if collection is None:
        return jsonify({"error": "MongoDB connection error."}), 500

    try:
        # Fetch multiple articles (example: limit to 20 articles)
        articles = collection.find().limit(20)

        # Create a list of article details
        article_list = []
        for article in articles:
            article_list.append({
                "URL": article.get('url', 'No URL'),
                "Title": article.get('title', 'No Title'),
                "Keywords": article.get('keywords', [])
            })

        return jsonify(article_list)

    except Exception as e:
        # Print the exception and return a 500 status code with error message
        print(f"An error occurred: {e}")
        return jsonify({"error": f"An error occurred while fetching article details: {e}"}), 500

@app.route('/articles_with_video', methods=['GET'])
def articles_with_video():
    if collection is None:
        return jsonify({"error": "MongoDB connection error."}), 500

    try:
        # Query the database for articles where video_duration is not null
        articles = collection.find({
            'video_duration': {'$ne': None} # $ne means "not equal to"
        })

        # Collect the titles of the articles that contain a video
        result = [article.get('title', 'No Title') for article in articles]

        # Check if no articles are found
        if not result:
            return jsonify({"message": "No articles with video found."}), 404

        return jsonify(result)

    except Exception as e:
        # Print the exception and return a 500 status code with error message
        print(f"An error occurred: {e}")
        return jsonify({"error": f"An error occurred while fetching articles with video: {e}"}), 500


@app.route('/articles_by_year/<int:year>', methods=['GET'])
def articles_by_year(year):
     # Query the database for articles published in the specified year
    count = collection.count_documents({
        "publication_date": {
            "$gte": f"{year}-01-01T00:00:00+00:00",
            "$lt": f"{year + 1}-01-01T00:00:00+00:00"
        }
    })

    # Format the response
    response = {f"{year} ({count} articles)": count}

    return jsonify(response)

@app.route('/longest_articles', methods=['GET'])
def longest_articles():
    if collection is None:
        return jsonify({"error": "MongoDB connection error."}), 500

    try:
        # Aggregate query to get the top 10 articles by word count
        pipeline = [
            {"$sort": {"word_count": -1}}, # Sort by word_count in descending order
            {"$group": {
                "_id": "$title", # Group by title to ensure uniqueness
                "word_count": {"$first": "$word_count"} # Get the word_count of the first document in each group
            }},
            {"$sort": {"word_count": -1}}, # Sort again after grouping
            {"$limit": 10}, # Limit to the top 10 articles
            {"$project": {"_id": 0, "title": "$_id", "word_count": 1}} # Format the output
        ]

        # Execute the aggregation pipeline
        result = list(collection.aggregate(pipeline))

        # Format the result
        formatted_result = [
            {"title": article.get('title', 'No Title'), "word_count": article.get('word_count', 0)}
            for article in result
        ]

        return jsonify(formatted_result)

    except Exception as e:
        # Print the exception and return a 500 status code with error message
        print(f"An error occurred: {e}")
        return jsonify({"error": f"An error occurred while fetching longest articles: {e}"}), 500

@app.route('/shortest_articles', methods=['GET'])
def shortest_articles():
    # Define the MongoDB aggregation pipeline
    pipeline = [
        {
            "$addFields": {
                "article_length": {
                    "$cond": {
                        "if": {
                            "$and": [
                                {"$ne": ["$article_text", None]}, # Check if the field is not None
                                {"$eq": [{"$type": "$article_text"}, "string"]} # Check if the field is a string
                            ]
                        },
                        "then": {"$strLenCP": "$article_text"}, # Calculate the length if it's a valid string
                        "else": None # If not, set to None
                    }
                }
            }
        },
        {
            "$sort": {"article_length": 1} # Sort articles by length (ascending)
        },
        {
            "$limit": 10 # Limit the result to the 10 shortest articles
        }
    ]

    # Execute the pipeline using MongoDB's aggregate method
    result = list(collection.aggregate(pipeline))

    # Convert the result to a JSON serializable format
    result = serialize_doc(result)

    # Return the result as JSON
    return jsonify(result)

@app.route('/articles_by_keyword_count', methods=['GET'])
def articles_by_keyword_count():
    pipeline = [
        {"$project": {"keyword_count": {"$size": "$keywords"}}},
        {"$group": {"_id": "$keyword_count", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]
    result = list(collection.aggregate(pipeline))
    return jsonify(result)

@app.route('/articles_with_thumbnail', methods=['GET'])
def articles_with_thumbnail():
    if collection is None:
        return jsonify({"error": "MongoDB connection error."}), 500

    try:
        # Query to find articles with a non-null thumbnail
        query = {"thumbnail": {"$exists": True, "$ne": None}}

        # Find articles matching the query
        articles = collection.find(query, {"title": 1, "_id": 0}) # Project only the title

        # Format the result
        formatted_result = [article.get('title', 'No Title') for article in articles]

        return jsonify(formatted_result)

    except Exception as e:
        # Print the exception and return a 500 status code with error message
        print(f"An error occurred: {e}")
        return jsonify({"error": f"An error occurred while fetching articles with thumbnail: {e}"}), 500

@app.route('/articles_updated_after_publication', methods=['GET'])
def articles_updated_after_publication():
    result = list(collection.find({"$expr": {"$gt": ["$last_updated", "$published_date"]}}))
    serialized_result = serialize_objectid(result)
    return jsonify(serialized_result)

@app.route('/articles_by_coverage/<coverage>', methods=['GET'])
def articles_by_coverage(coverage):
    result = list(collection.find({"classes": coverage}))
    return jsonify(result)


@app.route('/popular_keywords_last_X_days/<int:days>', methods=['GET'])
def popular_keywords_last_X_days(days):
    if collection is None:
        return "MongoDB connection error.", 500

    try:
        # Calculate the date range for the last X days
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        # Query to find articles published in the last X days
        pipeline = [
            {"$match": {
                "published_time": {"$gte": start_date, "$lte": end_date},
                "keywords": {"$exists": True}
            }},
            {"$unwind": "$keywords"},
            {"$group": {
                "_id": "$keywords",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}}
        ]

        # Execute the aggregation pipeline
        result = list(collection.aggregate(pipeline))

        # Aggregate keyword counts
        keyword_counter = Counter()
        for item in result:
            # Ensure the keywords are handled as a set for uniqueness
            keywords_list = item["_id"].split(",") # Adjust if your keywords are separated differently
            keywords_tuple = tuple(sorted(set(keywords_list))) # Sort and remove duplicates
            keyword_counter[keywords_tuple] += item["count"]

        # Format the results
        sorted_keywords = sorted(keyword_counter.items(), key=lambda x: x[1], reverse=True)
        formatted_result = [
            {"keywords": ", ".join(keywords), "count": count}
            for keywords, count in sorted_keywords
        ]

        return jsonify(formatted_result)

    except Exception as e:
        return f"An error occurred while fetching popular keywords: {e}", 500



@app.route('/articles_by_month/<int:year>/<int:month>', methods=['GET'])
def articles_by_month(year, month):
    if collection is None:
        return jsonify({"error": "MongoDB connection error."}), 500

    try:
        # Construct the start and end dates for the given month and year, assuming +03:00 timezone
        start_date = datetime(year, month, 1, 0, 0, 0) # No explicit timezone
        next_month = month % 12 + 1
        next_year = year + (month // 12)
        end_date = datetime(next_year, next_month, 1, 0, 0, 0) - timedelta(seconds=1)

        # Manually adjust the time to match the +03:00 timezone
        start_date = start_date.replace(tzinfo=timezone(timedelta(hours=3)))
        end_date = end_date.replace(tzinfo=timezone(timedelta(hours=3)))

        # Debug: Print the date range
        print(f"Date Range: Start Date - {start_date.isoformat()}, End Date - {end_date.isoformat()}")

        # Query to find articles published in the specified month and year
        pipeline = [
            {"$match": {
                "published_time": {"$gte": start_date, "$lte": end_date}
            }},
            {"$count": "article_count"}
        ]

        # Debug: Print the aggregation pipeline
        print(f"Aggregation Pipeline: {pipeline}")

        # Execute the aggregation pipeline
        result = list(collection.aggregate(pipeline))

        # Debug: Print the aggregation result
        print(f"Aggregation Result: {result}")

        # Extract count from the result
        count = result[0]["article_count"] if result else 0

        # Map month number to month name
        month_name = datetime(year, month, 1).strftime('%B')

        # Format the result
        formatted_result = {
            f"{month_name} {year}": f"({count} articles)"
        }

        return jsonify(formatted_result)

    except Exception as e:
        # Print the exception and return a 500 status code with error message
        print(f"An error occurred: {e}")
        return jsonify({"error": f"An error occurred while fetching articles by month: {e}"}), 500



@app.route('/articles_by_word_count_range/<int:min>/<int:max>', methods=['GET'])
def articles_by_word_count_range(min, max):
    pipeline = [
        {"$match": {"full_text": {"$exists": True, "$ne": ""}}},
        {"$project": {
            "word_count": {
                "$cond": {
                    "if": {"$gte": [{"$type": "$full_text"}, "string"]},
                    "then": {"$strLenCP": "$full_text"},
                    "else": 0
                }
            }
        }},
        {"$match": {"word_count": {"$gte": min, "$lte": max}}}
    ]
    result = list(collection.aggregate(pipeline))
    return jsonify(result)

@app.route('/articles_with_specific_keyword_count', methods=['GET'])
def articles_with_all_keyword_counts():
    if collection is None:
        return jsonify({"error": "MongoDB connection error."}), 500

    try:
        # Create an array to hold results for counts from 1 to 47
        results = []
        for count in range(1, 48):
            article_count = collection.count_documents({"keywords": {"$size": count}})
            results.append({
                "category": f"{count} keywords",
                "value": article_count
            })

        return jsonify(results)

    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({"error": f"An error occurred while fetching articles with specific keyword count: {e}"}), 500

@app.route('/articles_by_specific_date/<date>', methods=['GET'])
def articles_by_specific_date(date):
    if collection is None:
        return jsonify({"error": "MongoDB connection error."}), 500

    try:
        # Convert date from string to datetime object
        date_object = datetime.strptime(date, '%Y-%m-%d')

        # Query to find articles published on the specified date
        pipeline = [
            {"$match": {
                "published_time": {
                    "$gte": date_object,
                    "$lt": date_object + timedelta(days=1)
                }
            }},
            {"$count": "article_count"}
        ]

        # Print the aggregation pipeline for debugging
        print(f"Aggregation Pipeline: {pipeline}")

        # Execute the aggregation pipeline
        result = list(collection.aggregate(pipeline))

        # Print the result of the aggregation
        print(f"Aggregation Result: {result}")

        # Extract count from the result
        article_count = result[0]["article_count"] if result else 0

        # Format the result
        formatted_result = {
            f"Articles published on {date}": f"({article_count} articles)"
        }

        return jsonify(formatted_result)

    except Exception as e:
        # Print the exception and return a 500 status code with error message
        print(f"An error occurred: {e}")
        return jsonify({"error": f"An error occurred while fetching articles by specific date: {e}"}), 500


@app.route('/articles_containing_text/<text>', methods=['GET'])
def articles_containing_text(text):
    if collection is None:
        return jsonify({"error": "MongoDB connection error."}), 500

    try:
        # Use $regex with case-insensitive search
        regex = {"$regex": text, "$options": "i"} # "i" makes it case-insensitive

        # Construct the query
        query = {
            "$or": [
                {"title": regex},
                {"description": regex},
                {"keywords": {"$elemMatch": regex}} # Use $elemMatch with a regex object
            ]
        }

        # Debug: Print the query
        print(f"Search Query: {query}")

        # Execute the query
        results = list(collection.find(query))

        # Debug: Print the number of results found
        print(f"Number of articles found: {len(results)}")

        # Format results
        formatted_results = [
            {
                "id": str(article["_id"]), # Convert ObjectId to string
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "keywords": article.get("keywords", []),
                "published_time": article.get("published_time", ""),
                "description": article.get("description", ""),
                "author": article.get("author", "")
            }
            for article in results
        ]

        return jsonify(formatted_results)

    except Exception as e:
        # Print the exception and return a 500 status code with error message
        print(f"An error occurred: {e}")
        return jsonify({"error": f"An error occurred while fetching articles: {e}"}), 500


@app.route('/articles_with_more_than/<int:word_count>', methods=['GET'])
def articles_with_more_than(word_count):
    pipeline = [
        {
            "$match": {
                "word_count": {"$exists": True, "$ne": None} # Ensure word_count exists and is not None
            }
        },
        {
            "$addFields": {
                "numeric_word_count": {"$toInt": "$word_count"}
                # Convert word_count to an integer if stored as a string
            }
        },
        {
            "$match": {
                "numeric_word_count": {"$gt": word_count}
                # Filter articles with word count greater than the given number
            }
        }
    ]

    result = list(collection.aggregate(pipeline))
    return jsonify(result)


@app.route('/articles_grouped_by_coverage', methods=['GET'])
def articles_grouped_by_coverage():
    pipeline = [
        {"$unwind": "$classes"},
        {"$group": {"_id": "$classes", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]
    result = list(collection.aggregate(pipeline))
    return jsonify(result)

@app.route('/articles_by_author_and_date/<author_name>/<start_date>/<end_date>', methods=['GET'])
def articles_by_author_and_date(author_name, start_date, end_date):
    try:
        datetime.strptime(start_date, "%Y-%m-%d") # Validate date format
        datetime.strptime(end_date, "%Y-%m-%d")
        result = list(collection.find({
            "author": author_name,
            "published_date": {"$gte": start_date, "$lte": end_date}
        }))
        return jsonify(result)
    except ValueError:
        return jsonify({"error": "Invalid date format. Please use YYYY-MM-DD format."}), 400

@app.route('/articles_grouped_by_author', methods=['GET'])
def articles_grouped_by_author():
    pipeline = [
        {"$group": {"_id": "$author", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]
    result = list(collection.aggregate(pipeline))
    return jsonify(result)

@app.route('/articles_by_video_duration_range/<int:min_duration>/<int:max_duration>', methods=['GET'])
def articles_by_video_duration_range(min_duration, max_duration):
    result = list(collection.find({"video_duration": {"$gte": min_duration, "$lte": max_duration}}))
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True)

