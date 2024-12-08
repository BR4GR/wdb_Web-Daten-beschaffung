CREATE TABLE nutrients (
    id BIGSERIAL PRIMARY KEY,
    unit VARCHAR(15),
    quantity INT,
    kcal INT,
    kJ INT,
    fat VARCHAR(50),
    saturates VARCHAR(50),
    carbohydrate VARCHAR(50),
    sugars VARCHAR(50),
    fibre VARCHAR(50),
    protein VARCHAR(50),
    salt VARCHAR(50)
);


CREATE TABLE offer (
    id BIGSERIAL PRIMARY KEY,
    price DECIMAL(10, 2),
    quantity VARCHAR(50),
    unit_price DECIMAL(10, 2),
    promotion_price DECIMAL(10, 2),
    promotion_unit_price DECIMAL(10, 2)
);


CREATE TABLE category (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    path VARCHAR(100),
    slug VARCHAR(100)
);


CREATE TABLE product (
    id BIGSERIAL PRIMARY KEY,
    migros_id VARCHAR(30) NOT NULL,
    name VARCHAR(255) NOT NULL,
    brand VARCHAR(255),
    title VARCHAR(255),
    origin VARCHAR(255),
    description TEXT,
    ingredients TEXT,
    nutrient_id INT,
    offer_id INT,
    gtins TEXT,
    scraped_at TIMESTAMP,
    UNIQUE (migros_id, scraped_at),
    FOREIGN KEY (nutrient_id) REFERENCES nutrients(id),
    FOREIGN KEY (offer_id) REFERENCES offer(id)
);


CREATE TABLE product_category (
    product_id BIGINT,
    category_id INT,
    PRIMARY KEY (product_id, category_id),
    FOREIGN KEY (product_id) REFERENCES product(id),
    FOREIGN KEY (category_id) REFERENCES category(id)
);
