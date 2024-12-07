db = db.getSiblingDB('productsandcategories');

db.createCollection('products');
db.createCollection('categories');
db.createCollection('id_scraped_at');
db.createCollection('unit_price_history');
db.createCollection('request_counts');
