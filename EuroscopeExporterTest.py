# ===============================================================================================================#
#                                                                                                               #
#                                      VACC Switzerland GeoJSON Exporter                                        #
#                                                                                                               #
# ===============================================================================================================#
#                                                                                                               #
# Version 0.01 Alpha                                                                                            #
# Last revision: 2021-11-12                                                                                     #
# Changelog:                                                                                                    #
#   - 0.01                                                                                                      #
#       - New                                                                                                   #
# Known Issues:                                                                                                 #
#   - Polygons parsed to lines do not parse holes                                                               #
# To Do:                                                                                                        #
#   - Colour Listing for Jonas                                                                                  #
#   - Export capable for GNG                                                                                    #
#                                                                                                               #
# ===============================================================================================================#
#                                                                                                               #
# This is a basic converter / exporter that takes GeoJSON in a predefined format, applies a ruleset             #
# from a definitions file to it and from that generates a stub sector file that can be used for testing.        #
# In a second step a GNG compatible text file can be generated to easily import the generated data into         #
# an already established sectorfile.                                                                            #
#                                                                                                               #
# For conventions on the format of the input GeoJSON files check out the specification in the Ground Layouts    #
# oneDrive folder, additionally some further configuration of fields and attributes can be made through the     #
# definitions without touching the code.                                                                        #
#                                                                                                               #
# For questions or inquiries contact me at luca.paganini(at)vacc.ch                                             #
#                                                                                                               #
# ===============================================================================================================#

import argparse
from os import path, mkdir
from json import load
from re import search
from datetime import datetime
import math
import sys
from typing import List, Tuple
from pathlib import Path
from loguru import logger as logging

# Here we define a function to read the definitions file and then dump it into a global dict for easy access, and then run said function


def read_definitions(def_file_path: Path):
    with open(def_file_path, encoding="utf-8") as def_file:
        return load(def_file)


# This is a quick helper function to convert coordinates from QGIS (DDD.ddddd) to EuroScope (DDD.MM.SS.sss) Format and prefix the hemispheres


def decimal_degrees_to_es_notation(coordinate_pair: Tuple[float, float]):
    north = coordinate_pair[1]
    east = coordinate_pair[0]

    north_degrees = math.floor(math.fabs(north))
    north_minutes = math.floor((math.fabs(north) - north_degrees) * 60)
    north_seconds_raw = round(
        (math.fabs(north) - north_degrees - north_minutes / 60) * 3600, 3
    )

    north_seconds = str(north_seconds_raw)
    if north_seconds_raw < 10:
        north_seconds = "0" + str(north_seconds)

    formatted_north = (
        str(north_degrees).rjust(3, "0")
        + "."
        + str(north_minutes).rjust(2, "0")
        + "."
        + str(north_seconds).ljust(6, "0")
    )
    if north < 0:
        formatted_north = "S" + formatted_north
    else:
        formatted_north = "N" + formatted_north

    east_degrees = math.floor(math.fabs(east))
    east_minutes = math.floor((math.fabs(east) - east_degrees) * 60)
    east_seconds_raw = round(
        (math.fabs(east) - east_degrees - east_minutes / 60) * 3600, 3
    )

    east_seconds = str(east_seconds_raw)
    if east_seconds_raw < 10:
        east_seconds = "0" + str(east_seconds)

    formatted_east = (
        str(east_degrees).rjust(3, "0")
        + "."
        + str(east_minutes).rjust(2, "0")
        + "."
        + str(east_seconds).ljust(6, "0")
    )
    if east < 0:
        formatted_east = "W" + formatted_east
    else:
        formatted_east = "E" + formatted_east

    return formatted_north + " " + formatted_east


# This is the function that does most of the heavy lifting, it takes a dictionary that contains all the necessary data read from the geoJSON input file and
# mapped to more applicable categories through the definitions file and converts it into a multi-line string in the correct format for EuroScope


def format_feature_for_es(
    definitions: dict,
    feature_object,
    feature_type: str,
):
    coordinates = []

    # Initially we need to check which category of ES object we're writing to as the formatting conventions in EuroScope / VRC aren't exactly standardized
    # First step is to format the color of the object for Euroscope, as at least this part is common to all object formats

    color = feature_object["Color"]
    if not color.isdecimal():
        color = "COLOR_" + color

    # Secondly we check what kind of a feature type we're dealing with and extracting the coordinate list accordingly, this is necessary due to a nesting
    # quirk of GeoJSON where polygons are nested deeper than lines, which are nested deeper than points. The check for holes in polygons has already been
    # implemented, currently they're just assigned the color value of the backgrround as defined in definitions. This function also deals with "downgrading"
    # features between feature types, i.e. mapping a polygon to a line feature.

    logging.debug(
        "Feature Type of working feature is: " + feature_object["Feature Type"]
    )

    if len(feature_object["Coordinates"]) == 0:
        logging.error(
            "Found an empty feature of group " + feature_object["Group"] + ", skipping."
        )
        sys.exit(-1)
    if feature_object["Feature Type"] == "Polygon":
        if not (feature_type == "MultiPolygon" or feature_type == "Polygon"):
            logging.error(
                "Tried mapping a feature of group "
                + feature_object["Group"]
                + " that isn't a polygon to a Euroscope region.\n"
            )
            sys.exit(-1)
        if feature_type == "MultiPolygon":
            coordinates = feature_object["Coordinates"][0]
        if feature_type == "Polygon":
            coordinates = feature_object["Coordinates"]
    elif feature_object["Feature Type"] == "Line":
        if not feature_type == "MultiLineString":
            if feature_type == "MultiPolygon":
                logging.warning(
                    "Mapping a polygon feature of group "
                    + feature_object["Group"]
                    + " to a Euroscope geo line, holes may be lost in the process.\n"
                )
                coordinates = feature_object["Coordinates"][0]
            elif feature_type == "LineString":
                coordinates = [feature_object["Coordinates"]]
            else:
                logging.error(
                    "Tried mapping a point feature or a feature of unknown type of group "
                    + feature_object["Group"]
                    + " to a Euroscope geo line.\n"
                )
                sys.exit(-1)
        else:
            coordinates = feature_object["Coordinates"]
    elif feature_object["Feature Type"] == "Point":
        point_coordinates: Tuple[float, float] = (0.0, 0.0)
        if not feature_type == "Point":
            if feature_type == "MultiPolygon":
                logging.warning(
                    "Mapping a polygon feature of group "
                    + feature_object["Group"]
                    + " to a Euroscope freetext point, only the first coordinate will be considered.\n"
                )
                point_coordinates = feature_object["Coordinates"][0][0]
            if feature_type == "MultiLineString":
                logging.warning(
                    "Mapping a line feature of group "
                    + feature_object["Group"]
                    + " to a Euroscope freetext point, only the first coordinate will be considered.\n"
                )
                point_coordinates = feature_object["Coordinates"][0]
        else:
            point_coordinates = feature_object["Coordinates"]

        if feature_object["ES Category"] == "freetext":
            if "Label" in feature_object:
                output_text = (
                    decimal_degrees_to_es_notation(point_coordinates).replace(" ", ":")
                    + ":"
                    + feature_object["Group"]
                    + ":"
                    + feature_object["Label"]
                    + "\n"
                )
                return output_text
            else:
                logging.error(
                    "Missing label attribute for a freetext feature of group "
                    + feature_object["Group"]
                    + ", skipping feature.\n"
                )
                sys.exit(-1)
    else:
        logging.error(
            "Something went wrong with a feature object at "
            + feature_object["Group"]
            + " which has an invalid feature type ("
            + feature_object["Feature Type"]
            + ")"
        )
        sys.exit(-1)

    # Initially I deal with the regions as they are the most complex feature
    if feature_object["ES Category"] == "regions":
        # Here we assign a priority to certain layers. This should only be defined for regions layers
        if "Priority" in feature_object:
            priority = feature_object["Priority"]
        else:
            logging.error("Missing Priority")
            sys.exit(-1)

        # I create an empty dict with the priority and the formatted region to be filled by the subsequent functions

        feature_dict = {"Priority": priority, "Formatted Region": ""}
        logging.debug("This Region Feature has a length of " + str(len(coordinates)))

        # I have to make sure I catch any possible holes in the polygon, those would be a second item in the enclosing
        # list for the multipolygon feature in the geoJSON, so I iterate over the list containing the coordinate lists

        for i, current_coords_list in enumerate(coordinates):
            logging.debug(
                "  Currently working on layer "
                + str(i + 1)
                + "/"
                + str(len(coordinates))
            )

            # Set the color for all objects except for the base layer object to the defined hole color

            if not i == 0:
                logging.debug("    Setting Color to grass for hole")
                # color = "11823615"    # Hot Pink for debugging purposes
                color = "COLOR_" + definitions["Colors"]["Hole Color"]

            # Figure out what the first set of coordinates is as those are prefixed with the color for the entire region

            first_coords = decimal_degrees_to_es_notation(current_coords_list[0])

            # Create the string with the feature, initializing by creating the region name header and the first line with the color prefix

            coordinate_text = (
                "REGIONNAME "
                + feature_object["Group"]
                + "\n"
                + (color).ljust(27)
                + first_coords
                + "\n"
            )

            # For all further coordinates I can just chuck them into the string after justifying them according to the convention

            for coordinate_pair in current_coords_list[1:-1]:
                formatted_coords = decimal_degrees_to_es_notation(coordinate_pair)
                coord_string = formatted_coords.rjust(56) + "\n"
                coordinate_text += coord_string

            # Finally, I can append the created string to the feature dict

            feature_dict["Formatted Region"] += coordinate_text

        # And then return that feature dict to the calling function

        return feature_dict

    # in a second step I deal with all the lines which are categorized as GEO by EuroScope

    elif feature_object["ES Category"] == "geo":
        # Same principle as above, I need the first coordinate pair to prefix the feature name

        # Again here I initialize the string to be written into the sector file

        coordinate_text = ""
        for element in coordinates:
            first_coords = (
                decimal_degrees_to_es_notation(element[0])
                + " "
                + decimal_degrees_to_es_notation(element[1])
            )

            coordinate_text += (
                feature_object["Group"].ljust(41) + first_coords + " " + color + "\n"
            )

            # Now I iterate over all the elements in the coordinate list of the feature. As
            # EuroScope treats all lines as a group of individual line segments I need to draw each
            # segment, consisting of two coordinates, separately.

            for i in range(len(element) - 2):
                this_coord = decimal_degrees_to_es_notation(element[i + 1])
                next_coord = decimal_degrees_to_es_notation(element[i + 2])
                coordinate_text += (
                    (this_coord + " " + next_coord).rjust(100) + " " + color + "\n"
                )

        # Here I'm doing the lazy thing and only return the coordinate string, but I'll catch that in the next function

        return coordinate_text

    # And lastly, freetext, which is the simplest of the feature types as it only covers one point per item
    else:
        # If we're dealing with any other feature type (this should only happen with faulty definitions) I sys.exit(-1) to prevent the function calling
        # this from complaining.

        sys.exit(-1)


# And because it was so much fun we'll do it all over again, this time for GNG formatted items. There's a few formatting differences that I catch this way
# (namely, GNG knows no indenting), but for the most part the functions inside are identical.


def format_feature_for_gng(feature_object, feature_type: str):
    # Initially we need to check which category of ES object we're writing to as the formatting conventions in EuroScope / VRC aren't exactly standardized
    # First step is to format the color of the object for Euroscope, as at least this part is common to all object formats

    coordinates: List[List[Tuple[float, float]]] = []
    color = feature_object["Color"]
    if not color.isdecimal():
        color = "COLOR_" + color

    # Secondly we check what kind of a feature type we're dealing with and extracting the coordinate list accordingly, this is necessary due to a nesting
    # quirk of GeoJSON where polygons are nested deeper than lines, which are nested deeper than points. The check for holes in polygons has already been
    # implemented, they are currently assigned a fixed color from the definitions.

    logging.debug(
        "Feature Type of working feature is: " + feature_object["Feature Type"]
    )

    if len(feature_object["Coordinates"]) == 0:
        logging.error(
            "Found an empty feature of group " + feature_object["Group"] + ", skipping."
        )
        sys.exit(-1)
    if feature_object["Feature Type"] == "Polygon":
        if not (feature_type == "MultiPolygon" or feature_type == "Polygon"):
            logging.error(
                "Tried mapping a feature of group "
                + feature_object["Group"]
                + " that isn't a polygon to a Euroscope region.\n"
            )
            sys.exit(-1)
        if feature_type == "MultiPolygon":
            coordinates = feature_object["Coordinates"][0]
        if feature_type == "Polygon":
            coordinates = feature_object["Coordinates"]
    elif feature_object["Feature Type"] == "Line":
        if not feature_type == "MultiLineString":
            if feature_type == "MultiPolygon":
                logging.warning(
                    "Mapping a polygon feature of group "
                    + feature_object["Group"]
                    + " to a Euroscope geo line, holes may be lost in the process.\n"
                )
                coordinates = feature_object["Coordinates"][0]
            elif feature_type == "LineString":
                coordinates = [feature_object["Coordinates"]]
            else:
                logging.error(
                    "Tried mapping a point feature or a feature of unknown type of group "
                    + feature_object["Group"]
                    + " to a Euroscope geo line.\n"
                )
                sys.exit(-1)
        else:
            coordinates = feature_object["Coordinates"]
    elif feature_object["Feature Type"] == "Point":
        point_coordinates: Tuple[float, float] = (0.0, 0.0)
        if not feature_type == "Point":
            if feature_type == "MultiPolygon":
                logging.warning(
                    "Mapping a polygon feature of group "
                    + feature_object["Group"]
                    + " to a Euroscope freetext point, only the first coordinate will be considered.\n"
                )
                point_coordinates = feature_object["Coordinates"][0][0]
            if feature_type == "MultiLineString":
                logging.warning(
                    "Mapping a line feature of group "
                    + feature_object["Group"]
                    + " to a Euroscope freetext point, only the first coordinate will be considered.\n"
                )
                point_coordinates = feature_object["Coordinates"][0]
        else:
            point_coordinates = feature_object["Coordinates"]

        if feature_object["ES Category"] == "freetext":
            if "Label" in feature_object:
                airport_ICAO = feature_object["Group"][:4]
                labelgroup = feature_object["Group"][5:]
                output_text = (
                    decimal_degrees_to_es_notation(point_coordinates).replace(" ", ":")
                    + "::"
                    + feature_object["Label"]
                )
                feature_dict = {
                    "Group": feature_object["Group"],
                    "Airport": airport_ICAO,
                    "Labelgroup": labelgroup,
                    "Code": output_text,
                }
                return feature_dict
            else:
                logging.error(
                    "Missing label attribute for a freetext feature of group "
                    + feature_object["Group"]
                    + ", skipping feature.\n"
                )
                sys.exit(-1)
    else:
        logging.error(
            "Something went wrong with a feature object at "
            + feature_object["Group"]
            + " which has an invalid feature type ("
            + feature_object["Feature Type"]
            + ")"
        )
        sys.exit(-1)

    # Initially I deal with the regions as they are the most complex feature

    if feature_object["ES Category"] == "regions":
        if "Priority" in feature_object:
            priority = feature_object["Priority"]
        else:
            logging.error("Missing Priority")
            sys.exit(-1)

        # I create an empty dict with the priority and the formatted region to be filled by the subsequent functions

        feature_dict = {
            "Priority": priority,
            "RegionName": feature_object["Group"],
            "Formatted Region": "",
        }
        logging.debug("This Region Feature has a length of " + str(len(coordinates)))

        # I have to make sure I catch any possible holes in the polygon, those would be a second item in the enclosing
        # list for the multipolygon feature in the geoJSON, so I iterate over the list containing the coordinate lists

        for i, current_coords_list in enumerate(coordinates):
            logging.debug(
                "  Currently working on layer "
                + str(i + 1)
                + "/"
                + str(len(coordinates))
            )
            # Set the color for all objects except for the base layer object to grass

            if not i == 0:
                logging.debug("    Setting Color to grass for hole")
                # color = "11823615"    # Hot Pink for debugging purposes
                color = "COLOR_AoRground1"

            # Create the string with the feature, initializing by creating the region name header and the first line with the color prefix

            coordinate_text = color + "\n"

            # For all further coordinates I can just chuck them into the string after justifying them according to the convention

            for coordinate_pair in current_coords_list:
                formatted_coords = decimal_degrees_to_es_notation(coordinate_pair)
                coord_string = formatted_coords + "\n"
                coordinate_text += coord_string

            # Finally, I can append the created string to the feature dict

            feature_dict["Formatted Region"] += coordinate_text

        # And then return that feature dict to the calling function

        return feature_dict

    # in a second step I deal with all the lines which are categorized as GEO by EuroScope

    elif feature_object["ES Category"] == "geo":
        # Same principle as above, I need the first coordinate pair to prefix the feature name

        # Again here I initialize the string to be written into the sector file
        airport_ICAO = feature_object["Group"][:4]
        rest_of_group = feature_object["Group"][5:].rsplit(" ")
        feature_dict = {
            "Group": feature_object["Group"],
            "Airport": airport_ICAO,
            "Category": rest_of_group[0],
            "Name": " ".join(rest_of_group[1:]),
            "Code": "",
        }
        for element in coordinates:
            # Now I iterate over all the elements in the coordinate list of the feature. As
            # EuroScope treats all lines as a group of individual line segments I need to draw each
            # segment, consisting of two coordinates, separately.

            for i in range(len(element) - 1):
                this_coord = decimal_degrees_to_es_notation(element[i])
                next_coord = decimal_degrees_to_es_notation(element[i + 1])
                feature_dict["Code"] += (
                    (this_coord + " " + next_coord) + " " + color + "\n"
                )

        # Here I'm doing the lazy thing and only return the coordinate string, but I'll catch that in the next function

        return feature_dict

    # And lastly, freetext, which is the simplest of the feature types as it only covers one point per item

    # If we're dealing with any other feature type (this should only happen with faulty definitions) I sys.exit(-1) to prevent the function calling
    # this from complaining.

    sys.exit(-1)


# This is just a helper function to assign a feature its attributes from the definitions file


def category_mapping(category: str, airport: str):
    # If the category is not defined it can obviously not be mapped so we write to the log file and skip out of the function

    if category is None:
        logging.error("Skipping feature because of missing category in file ")
        sys.exit(-1)

    # First I split the category string into the main category and the suffixes

    split_cat = category.split("_")
    main_category = split_cat[0]

    # Then I try mapping the object through the definitions to get the default state of the main category. If the category isn't defined in the
    # definitions file we once again skip out of the function

    if not main_category in definitions["Category Mapping"]:
        logging.error("Unknown category " + main_category + " found in file ")
        sys.exit(-1)
    mapped_object = definitions["Category Mapping"][main_category]
    output_object = dict(mapped_object["default"])

    logging.debug(
        "Input Category: " + category + "\n  Default Group: " + output_object["Group"]
    )

    # If I have found any suffixes I'll iterate through them and look for them in the definitions file, if they're defined we overwrite the default
    # info with the suffix info where it differs.

    if len(split_cat) > 1:
        # Because grass features sometimes lead to trouble here's an easy way to make sure they're actually found by the script
        if "gr" in split_cat:
            logging.debug(
                "Found a Grass feature for airport " + airport + str(split_cat)
            )

        suffix = split_cat[1]

        logging.debug("  Now working on suffix " + suffix)

        # If a suffix doesn't exist for a certain category that has to be caught which is done with this function
        if not suffix in mapped_object["suffixes"]:
            logging.error(
                "Unknown suffix "
                + suffix
                + " to category "
                + main_category
                + " found in file "
            )
            sys.exit(-1)

        suffix_description = mapped_object["suffixes"][suffix]
        for key in suffix_description:
            if not key == "Additional Suffixes":
                output_object[key] = suffix_description[key]
                if len(split_cat) > 2:
                    if search("([0-3]{1}[0-9]{1}[LCR]?)", split_cat[2]):
                        output_object["Group"] = output_object["Group"].replace(
                            "$1", split_cat[-1]
                        )
                    else:
                        logging.warning(
                            "Unmappable additional suffix "
                            + split_cat[2]
                            + " found in "
                            + category
                        )
            elif len(split_cat) > 2:
                if not search("([0-3]{1}[0-9]{1}[LCR]?)", suffix):
                    for additional_suffix in suffix_description["Additional Suffixes"]:
                        if additional_suffix in split_cat:
                            for additional_key in suffix_description[
                                "Additional Suffixes"
                            ][additional_suffix]:
                                output_object[additional_key] = suffix_description[
                                    "Additional Suffixes"
                                ][additional_suffix][additional_key]
                else:
                    output_object["Group"] = output_object["Group"].replace(
                        "$1", split_cat[-1]
                    )

    # The Group attribute often contains an airport tag so we replace it in here already
    output_object["Group"] = output_object["Group"].replace("$airport", airport)

    logging.debug(
        "Output:\n  Group: "
        + output_object["Group"]
        + "\n  ES Category: "
        + output_object["ES Category"]
    )

    # If everything worked fine we can now return the object we just created wit the mapped info

    return output_object


# Another helper function to transform hex codes into Euroscope decimal 24bit color integers. Because I'm only working with strings to build the output
# file I return the integer as a string


def es_color_code(color_hex):
    hex_string = color_hex[1:]
    red = int(hex_string[0:2], 16)
    green = int(hex_string[2:4], 16)
    blue = int(hex_string[4:], 16)
    dec_string = str(blue * 65536 + green * 256 + red)
    logging.debug(
        "Color Hex value #"
        + hex_string
        + " converted to Red: "
        + str(red)
        + ", Green: "
        + str(green)
        + ", Blue: "
        + str(blue)
    )
    return dec_string


# This is one of the big bois, it reads a single GeoJSON file and parses it into the respective categories


def read_geo_json_file(
    colors_used: List[str],
    es_data: dict,
    gng_data: dict,
    definitions: dict,
    json_path: Path,
):
    # The first and most obvious step is to actually open and load the file into a dict courtesy of the json library

    with open(json_path, encoding="utf-8") as json_file:
        data = load(json_file)

    # Next we step through each feature in the data we loaded. We can safely discard the header as all the information in there is not necessary for our purposes

    for feature in data["features"]:
        # If there is no geometry defined for the feature it's not relevant for us, we can skip that.

        if feature["geometry"] is None:
            continue

        # I noticed that QGIS sometimes decides to capitalize the keys so here I make them all lowercase so that I can access them easily

        feature["properties"] = {
            key.lower(): value for key, value in feature["properties"].items()
        }

        # Load a few key properties as easily accessed variables

        airport = feature["properties"]["apt"]
        label = feature["properties"]["lbl"]
        color = feature["properties"]["clr"]
        category = feature["properties"]["cat"]
        feature_type = feature["geometry"]["type"]

        # If attributes are missing we cannot parse the feature so we log that and skip the feature

        if airport is None:
            logging.warning(
                'Skipping feature because of missing "apt" attribute in file '
                + str(json_path)
            )
            continue

        if "_dis" in category:
            logging.warning("Skipping disabled feature in file " + str(json_path))
            continue

        # Now let's use that helper function to map category of the current feature to the attributes found in the definitions

        feature_object = category_mapping(category, airport)

        # If the function fails it will append the log with how it failed but it doesn't know what file it failed on so we write that into the log here.

        if feature_object == -1:
            logging.debug(json_path)
            continue

        # Some features aren't intended for use in EuroScope so we ignore them.

        if "Ignore" in feature_object:
            if feature_object["Ignore"]:
                continue

        # Next, let's extract the coordinates of the feature as well. I only do this now to prevent issues with null items

        coordinates = feature["geometry"]["coordinates"]

        # Now we can add a few additional attributes to the feature object that are needed for some subfunctions

        feature_object["Label"] = label
        feature_object["Coordinates"] = coordinates

        # If we have a color assigned in the feature we'll have to overwrite the default colour from the definition

        if not color is None:
            logging.debug("Setting custom color " + color)

            # First let's deal with anything that isn't a hex code as we need to look those up.

            if not search("#[0-9a-fA-F]{6}", color):
                # This checks for custom defined two letter color codes specified in the definitions, this is used as a
                # shortcut to create new colors not yet defined in the sectorfile
                if search("^[a-z]{2}$", color):
                    for def_color in definitions["Colors"]["Additional Colors"]:
                        if def_color["Tag"] == color:
                            feature_object["Color"] = def_color["Color"]

                            logging.debug(
                                "  Custom Color " + feature_object["Color"] + " set!"
                            )

                # Any other color *should* be one already defined in the sector file so we can just write it into field

                else:
                    feature_object["Color"] = color
                    logging.debug("  Custom Color " + feature_object["Color"] + " set!")

            # Here we deal with the hex code defined colors, they're just passed to the appropriate function.

            else:
                feature_object["Color"] = es_color_code(color)
                logging.debug("  Custom Color " + feature_object["Color"] + " set!")

        # This is a little bit of a special case, there's a few definitions that use hex codes by default, we need to catch those

        elif search("#[0-9a-fA-F]{6}", feature_object["Color"]):
            feature_object["Color"] = es_color_code(feature_object["Color"])

        # And now that we have dealt with all the preparation we can pass the feature to the formatter

        if not feature_object["Color"] in colors_used:
            colors_used.append(feature_object["Color"])

        formatted_feature = format_feature_for_es(
            definitions, feature_object, feature_type
        )
        gng_formatted_feature = format_feature_for_gng(feature_object, feature_type)

        # After the feature has been formatted it is then sorted into the correct category

        if not formatted_feature == -1:
            # logging.info("Key: " + gngformatted_feature["RegionName"] + "\nObject: " + dumps(gng_data[feature_object["ES Category"]]["Features"],indent=1))
            if feature_object["ES Category"] == "regions":
                es_data[feature_object["ES Category"]]["Features"].append(
                    formatted_feature
                )
                if (
                    gng_formatted_feature["RegionName"]
                    in gng_data[feature_object["ES Category"]]["Features"]
                ):
                    gng_data[feature_object["ES Category"]]["Features"][
                        gng_formatted_feature["RegionName"]
                    ].append(gng_formatted_feature)
                else:
                    gng_data[feature_object["ES Category"]]["Features"][
                        gng_formatted_feature["RegionName"]
                    ] = [gng_formatted_feature]
            else:
                es_data[feature_object["ES Category"]][
                    "Output String"
                ] += formatted_feature
                if (
                    gng_formatted_feature["Group"]
                    in gng_data[feature_object["ES Category"]]["Features"]
                ):
                    gng_data[feature_object["ES Category"]]["Features"][
                        gng_formatted_feature["Group"]
                    ]["Code"] += ("\n" + gng_formatted_feature["Code"])
                else:
                    gng_data[feature_object["ES Category"]]["Features"][
                        gng_formatted_feature["Group"]
                    ] = gng_formatted_feature
        else:
            logging.warning(
                "Skipping feature due to error in formatting from file "
                + str(json_path)
            )


# Regions need to be sorted so that the layering is correct, this is accomplished by sorting the array on the priority attribute
# from the definitions file


def sort_regions(
    es_data: dict,
    gng_data: dict,
    target: str = "euroscope",
):
    if target == "euroscope":
        sorted_list = sorted(
            es_data["regions"]["Features"], key=lambda x: x["Priority"]
        )
        es_data["regions"]["Features"] = sorted_list

        for feature in sorted_list:
            es_data["regions"]["Output String"] += feature["Formatted Region"]
    elif target == "gng":
        for key in gng_data["regions"]["Features"]:
            gngsorted_list: List[dict] = sorted(
                gng_data["regions"]["Features"][key], key=lambda x: x["Priority"]
            )
            gng_data["regions"]["Features"][key] = {
                "Output String": "",
                "Features": list(gngsorted_list),
            }

            for feature in gngsorted_list:
                gng_data["regions"]["Features"][key]["Output String"] += (
                    feature["Formatted Region"] + "\n"
                )
    else:
        logging.warning(
            "Something broke while sorting, check target "
            + target
            + " is correct, because the code is stukkie wukkie, mss could you better sort by hand owo."
        )


# This is the function that reads the entire folder and finds all the readable files in there, then reads them one by one


def read_folder(
    colors_used: List[str],
    es_data: dict,
    gng_data: dict,
    definitions: dict,
    folder_path: Path,
):
    files = folder_path.glob("*/*.geojson")
    for file in files:
        logging.info("Reading file " + file.name + " in folder " + str(file.parent))
        read_geo_json_file(
            colors_used,
            es_data,
            gng_data,
            definitions,
            file,
        )


# This is another helper function that converts color codes back from ES decimal format into a "human readable" hex code


def hex_color_code(decimal_color: int):
    """Convert integer dcolors to the hex format"""

    blue = int(decimal_color / 65536)
    green = int((decimal_color - (blue * 65536)) / 256)
    red = decimal_color - (blue * 65536) - (green * 256)
    color_hex = (
        "#"
        + hex(red)[2:].ljust(2, "0")
        + hex(green)[2:].ljust(2, "0")
        + hex(blue)[2:].ljust(2, "0")
    )
    return color_hex


# From here on out we just need to write the files, first the sct file which also needs the color definitions from the definitions file


def write_sct_file(output_folder: Path, es_data: dict):
    """Write out the sct file"""

    sct_file_path = output_folder / (
        "QGIS_Generated_Sectorfile-" + date_string_long + ".sct"
    )

    geo = es_data["geo"]["Output String"]
    regions = es_data["regions"]["Output String"]
    colors = ""

    for sector_file_color in definitions["Colors"]["Sector File Colors"]:
        colors += (
            ("#define COLOR_" + sector_file_color["Name"]).ljust(30)
            + es_color_code(sector_file_color["Hex"]).rjust(9)
            + "\n"
        )

    with open(sct_header_path, encoding="utf-8") as sct_header:
        contents = (
            sct_header.read()
            .replace("$date     ", date_string)
            .replace("$date", date_string)
            .replace("$regions", regions)
            .replace("$geo", geo)
            .replace("$colors", colors)
        )

    with open(sct_file_path, "w", encoding="utf-8") as generated_sectorfile:
        generated_sectorfile.write(contents)


# Next we write the ese file


def write_ese_file(output_folder: Path, es_data):
    """Write out the ese file"""

    ese_file_path = output_folder / (
        "QGIS_Generated_Sectorfile-" + date_string_long + ".ese"
    )

    freetext = es_data["freetext"]["Output String"]

    with open(ese_header_path, encoding="utf-8") as ese_header:
        contents = (
            ese_header.read()
            .replace("$date     ", date_string)
            .replace("$date", date_string)
            .replace("$freetext", freetext)
        )

    with open(ese_file_path, "w", encoding="utf-8") as generated_sectorfile:
        generated_sectorfile.write(contents)


# And finally a bit of a different approach for the GNG text files, here we have a file handling function that only deals with the actual file operations


def write_gng_file(output_folder: Path, file_type: str, string: str):
    """Write out the gng file"""

    gng_regions_file_path = output_folder / (
        "GNG_" + file_type + "_Export-" + date_string_long + ".txt"
    )
    with open(gng_regions_file_path, "w", encoding="utf-8") as gng_regions_file:
        gng_regions_file.write(string)


# While down here we deal with getting the features actually formatted to the GNG conventions


def format_for_gng(output_folder: Path, es_data: dict, gng_data: dict):
    """Format the data in the gng format"""

    sort_regions(es_data, gng_data, "gng")
    for layer in gng_data["regions"]["Features"]:
        airport = layer[:4]
        layername = layer[5:]
        header = "AERONAV:" + airport + ":" + layername + ":ES,VRC:QGIS " + AIRAC + "\n"
        gng_data["regions"]["Output String"] += (
            header + gng_data["regions"]["Features"][layer]["Output String"] + "\n"
        )
    for layer_name in gng_data["geo"]["Features"]:
        layer = gng_data["geo"]["Features"][layer_name]
        airport = layer["Airport"]
        category = layer["Category"]
        name = layer["Name"]
        header = ":".join(
            ["AERONAV", airport, category, name, "", "GEO", "", "QGIS " + AIRAC + "\n"]
        )
        gng_data["geo"]["Output String"] += header + layer["Code"] + "\n"
    for layer_name in gng_data["freetext"]["Features"]:
        layer = gng_data["freetext"]["Features"][layer_name]
        airport = layer["Airport"]
        labelgroup = layer["Labelgroup"]
        header = ":".join(
            ["AERONAV", airport, labelgroup, "ES-ESE", "QGIS " + AIRAC + "\n"]
        )
        gng_data["freetext"]["Output String"] += header + layer["Code"] + "\n\n"
    for file_type, data in gng_data.items():
        write_gng_file(output_folder, file_type, data["Output String"])


if __name__ == "__main__":
    # First, to facilitate parsing, create a dictionary that holds all entries, split into the different ES
    # categories used. This dict is initialized empty to prevent issues with python variable handling
    # The AIRAC variable is used to create the GNG comment that is used to keep track of when changes were inserted,
    # at VACC CH the value thereof is always that of the Cycle when the changes will be published (thus usually one cycle ahead).

    AIRAC = "2308"

    es_data = {
        "geo": {"Output String": "", "Features": []},
        "freetext": {"Output String": "", "Features": []},
        "regions": {"Output String": "", "Features": []},
    }

    gng_data = {
        "geo": {"Output String": "", "Features": {}},
        "freetext": {"Output String": "", "Features": {}},
        "regions": {"Output String": "", "Features": {}},
    }

    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.remove()
    logging.add(sys.stderr, level="DEBUG" if args.verbose else "INFO")

    logging.info(
        "Started Logging at "
        + datetime.now().strftime("%Y-%m-%d, %H:%M:%S")
        + " at logging level "
        + "DEBUG"
        if args.verbose
        else "INFO"
    )

    colors_used: List[str] = []

    # I create two strings with the current date, this is important as it's used in the output file name and the .sct and .ese files need to have exactly the same name

    date_string = datetime.now().strftime("%Y-%m-%d")
    date_string_long = datetime.now().strftime("%Y%m%d-%H%M%S")

    # Here a few file and path definitions.

    # Definitions file, used to create rules for parsing
    def_file_path = Path.cwd() / "Input/Configuration/ES Exporter Definitions.json"
    # Input GeoJSON location
    geo_json_folder_path = Path.cwd() / "Input/GeoJSON/"
    # Input of the sct Header file used as a basis for building the export
    sct_header_path = Path.cwd() / "Input/Configuration/sct_File_Header.txt"
    # Input of the ese Header file used as a basis for building the export
    ese_header_path = Path.cwd() / "Input/Configuration/ese_File_Header.txt"
    # Output folder location
    output_folder = Path.cwd() / "Output/"

    logging.debug(
        "Folder paths:\n  Definitions File: "
        + str(def_file_path)
        + "\n  geoJSON Folder: "
        + str(geo_json_folder_path)
        + "\n  .SCT  header File: "
        + str(sct_header_path)
        + "\n  .ESE  header File: "
        + str(ese_header_path)
        + "\n  Output Folder: "
        + str(output_folder)
    )

    # Here we check whether the output folder exists, if not we create it.

    if not path.isdir(output_folder):
        mkdir(output_folder)
        logging.info("Creating output folder at " + str(output_folder))
    definitions = read_definitions(def_file_path)
    read_folder(
        colors_used,
        es_data,
        gng_data,
        definitions,
        geo_json_folder_path,
    )

    sort_regions(es_data, gng_data)

    write_sct_file(output_folder, es_data)
    write_ese_file(output_folder, es_data)
    format_for_gng(output_folder, es_data, gng_data)

    # And lastly, a bit of a dummy check, if there's any colours that were used in the sector filed that are not defined in GNG
    # this will note that down in the log file, as this can lead to hard to trace errors in Euroscope's file reading.

    for color in colors_used:
        if color == "":
            continue
        FOUND = False
        for entry in definitions["Colors"]["Sector File Colors"]:
            if entry["Name"] == color:
                FOUND = True
        if not FOUND:
            logging.warning("Color " + color + " either misspelled or not defined!")
