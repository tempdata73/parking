from configparser import ConfigParser


def config(filename, section):
    # read file
    parser = ConfigParser()
    parser.read(filename)
    # fetch data
    db ={}
    for params in parser.items(section):
        db[params[0]] = params[1]
    
    return db
