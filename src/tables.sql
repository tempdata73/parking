-- We'll need PostGIS for interpreting spatial data and locations
CREATE EXTENSION postgis;

-- The tables will be used so as to create some log info
-- especially in the cameras table
CREATE TABLE cameras (
    id integer PRIMARY KEY,
    location text NOT NULL,
    resolution_x integer,
    resolution_y integer,
    fps integer
);

CREATE TABLE spots (
    id SERIAL PRIMARY KEY,
    camera_id integer NOT NULL,
    location geometry NOT NULL,
    -- Actual information we might be interested in
    is_occupied boolean,
    is_overtime boolean,
    -- If camera is no longer available, delete records
    -- that reference to it
    CONSTRAINT camera_fkey FOREIGN KEY (camera_id)
                           REFERENCES cameras (id)
                           ON DELETE CASCADE
                           ON UPDATE CASCADE
);
