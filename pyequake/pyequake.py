from datetime import datetime as dt
from functools import cached_property
from typing import Union
import requests
import xml.etree.ElementTree as ET

ENDPOINT_URL = "https://earthquake.usgs.gov/fdsnws/event/1/{}"
ALLOWED_METHODS = {"query", "application.wadl"}


def convert_to_utc_str(func):
    """
    decorate methods with this higher-order function
    to convert inputs of function to UTC string.
    """

    def convert_to_utc_str_helper(date: Union[dt, str]) -> str:
        """
        helper function for func_wrapper.
        converts a datetime object to UTC formatted str.
        converts YYYY-MM-DD string to UTC formatted str.
        """
        utc_format = "%Y-%m-%dT%H:%M:%S"
        if isinstance(date, dt):
            date = date.strftime(utc_format)
        elif isinstance(date, str):
            utc_format_date = date + "T00:00:00"
            dt.strptime(utc_format_date, utc_format)
        else:
            raise TypeError(f"{date} must be datetime object or string")
        return date

    def func_wrapper(self, *args, **kwargs):
        """
        wrapper that converts input to utc string.
        """
        new_args = [
            convert_to_utc_str_helper(arg) for arg in args if arg is not None
        ]
        new_kwargs = {
            key: convert_to_utc_str_helper(val)
            for key, val in kwargs.items()
            if val is not None
        }
        res = func(self, *new_args, **new_kwargs)
        return res

    return func_wrapper


class QuakeQuery:

    fields_url = ENDPOINT_URL.format("application.wadl")
    query_url = ENDPOINT_URL.format("query")

    def __init__(self):
        self._session = requests.session()
        self._params = self.parse_endpoint_xml_params()
        self.query = {}

    def parse_endpoint_xml_params(self):
        """
        parse the parameters of the API XML doc
        """
        data = {}
        resp = requests.get(self.fields_url)
        root = ET.fromstring(resp.text)
        for param in root.iter("{http://wadl.dev.java.net/2009/02}param"):
            for nv_attrib in param.iter():
                nv_attrib = nv_attrib.attrib
                if "name" in nv_attrib:
                    name = nv_attrib["name"]
                    if "type" in nv_attrib:
                        xml_dtype = nv_attrib["type"]
                    else:
                        xml_dtype = "xs:string"
                        # if there are values associated with param
                        # they do not declare a type
                        # but it is a string
                    if "default" in nv_attrib:
                        default = nv_attrib["default"]
                    else:
                        default = None
                    data[name] = {"dtype": xml_dtype, "default": default}
                else:  # values for the previous name
                    value = nv_attrib["value"]
                    if "value" in data[name]:
                        data[name]["values"].append(value)
                    else:
                        data[name]["values"] = [value]
        return data

    @cached_property
    def params(self):
        return [field for field in self._params]

    def get_param_info(self, param: str):
        if param not in self.params:
            raise ValueError(
                f"Your parameter: {param} must be one "
                f"of the following values: {', '.join(self.params)}"
            )
        else:
            return self._params[param]

    def response_format(self, fmt: str = ""):
        """
        sets the format param for self.query.
        Determines format of response/output.
        Args:
            format:
                accepted values are csv, geojson, kml, quakeml, text, xml
            csv - CSV. Mime-type is “text/csv”.
            geojson - GeoJSON. Mime-type is “application/json”.
            kml - KML. Mime-type is “vnd.google-earth.kml+xml”.
            quakeml - Alias for "xml" format.
            text - plain text. Mime-type is “text/plain”.
            xml - Quakeml 1.2. Mime-type is "application/xml".
        Returns:
            self
        Raises:
            ValueError
        """
        if not isinstance(fmt, str):
            raise TypeError(f"fmt: '{fmt}' must be type string.")
        accepted = ["csv", "geojson", "kml", "quakeml", "text", "xml"]
        if fmt not in accepted:
            raise ValueError(
                f"fmt: '{fmt}' must be one of these values:"
                f"{', '.join(accepted)}"
            )
        self.query["format"] = fmt
        return self

    @convert_to_utc_str
    def occur_between(self, start: Union[dt, str], end=None):
        """
        sets startime and endtime params for self.query
        Args:
            start:
                limits events on or after start time.
                currently supports datetime OR string in format YYYY-MM-DD
            end:
                limits events on or before end time.
                If None, no param added to self.query and defaults to NOW.
                currently supports datetime OR string in format YYYY-MM-DD
        Returns:
            self

        Raises:
            TypeError if str or dt type not passed
            ValueError if string not in format "YYYY-MM-DD"
        """
        self.query["starttime"] = start
        if end is not None:
            self.query["endtime"] = end  # goes to default
        return self

    @convert_to_utc_str
    def updated_after(self, updated_after: dt):
        """
        sets updatedafter params for self.query
        Args:
            updated_after:
                Limit to events updated after specified time.
                currently supports datetime OR string in format YYYY-MM-DD
        Returns:
            self

        Raises:
            ValueError if str or dt type not passed
            or string not in format "YYYY-MM-DD"
        """
        self.query["updatedafter"] = updated_after
        return self

    def get(self):
        self.query["format"] = "geojson"
        response = self._session.get(self.query_url, params=self.query)
        return response


if __name__ == "__main__":
    qq = QuakeQuery()
    qq = qq.occur_between(dt(2021, 11, 12), "2021-11-13")
    response = qq.get()
    print(response.text)
