#! /usr/bin/env python
#-*- coding: utf-8 -*-
###########################################################################
##                                                                       ##
## Copyrights Etienne Chové <chove@crans.org> 2009                       ##
##                                                                       ##
## This program is free software: you can redistribute it and/or modify  ##
## it under the terms of the GNU General Public License as published by  ##
## the Free Software Foundation, either version 3 of the License, or     ##
## (at your option) any later version.                                   ##
##                                                                       ##
## This program is distributed in the hope that it will be useful,       ##
## but WITHOUT ANY WARRANTY; without even the implied warranty of        ##
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         ##
## GNU General Public License for more details.                          ##
##                                                                       ##
## You should have received a copy of the GNU General Public License     ##
## along with this program.  If not, see <http://www.gnu.org/licenses/>. ##
##                                                                       ##
###########################################################################

###########################################################################
## database connection

import sys, os, time, cgi, re
root_folder = os.environ["OSMOSE_ROOT"]
sys.path.append(root_folder)
from tools import utils

import cgitb
cgitb.enable()

PgConn   = utils.get_dbconn()
PgCursor = PgConn.cursor()

form    = cgi.FieldStorage()
source  = form.getvalue("source", None)
class_  = form.getvalue("class", None)
item    = form.getvalue("item", None)
country = form.getvalue("country", None)
num_points = form.getvalue("points", None)

if source:
    source = int(source)
if class_:
    class_ = int(class_)
if item:
    item   = int(item)
if country and not re.match(r"^([a-z_]+)$", country):
    country = None
if num_points:
    num_points = int(num_points)
    if num_points <= 0:
        num_points = None
    elif num_points > 10000:
        num_points = 10000

if "info" in os.environ["SCRIPT_NAME"]:
    gen = "info"
    default_show_all = True
elif "false-positive" in os.environ["SCRIPT_NAME"]:
    gen = "false-positive"
    default_show_all = False
elif "done" in os.environ["SCRIPT_NAME"]:
    gen = "done"
    default_show_all = False
else:
    sys.exit(0)

show_all = form.getvalue("all", None)

if show_all == None:
    show_all = default_show_all
elif int(show_all) == 0:
    show_all = False
else:
    show_all = True


lang_def = utils.allowed_languages[0]
lang_cur = utils.get_language()
translate = utils.translator()

###########################################################################
## page headers

utils.print_header()

query = os.environ["QUERY_STRING"]

print "<a href=\"info.py?%s\">Informations</a> <a href=\"done.py?%s\">Corrigé</a> <a href=\"false-positive.py?%s\">Faux positifs</a>" % ((query,) * 3)
print "<a href=\"graph.py?%s\">Graphe</a> <a href=\"/map/?%s\">Carte</a>" % ((query,) * 2)
print "<br><br>"

###########################################################################

print "<form method='get'>"

print "<select name='country'>"
print "<option value=''></option>"
sql = """
SELECT DISTINCT
  (string_to_array(comment,'-'))[array_upper(string_to_array(comment,'-'), 1)] AS country
FROM dynpoi_source
ORDER BY country;"""
PgCursor.execute(sql)
for res in PgCursor.fetchall():
    if country == res['country']:
        s = " selected='yes'"
    else:
        s = ""
    print "<option%s value='%s'>%s</option>" % (s, res['country'], res['country'])
print "</select>"

print "<select name='item'>"
print "<option value=''></option>"
sql = """
SELECT
  item,
  (CASE WHEN menu_%s IS NOT NULL
        THEN menu_%s
        ELSE menu_%s
   END) AS menu
FROM dynpoi_item
ORDER BY item;""" % (lang_cur, lang_cur, lang_def)
PgCursor.execute(sql)
for res in PgCursor.fetchall():
    if item == res['item']:
        s = " selected='yes'"
    else:
        s = ""
    print "<option%s value='%s'>%s - %s</option>" % (s, res['item'], res['item'], res['menu'])
print "</select>"
print "<input type='submit' value='Set'/>"

print "</form>"

###########################################################################

sql = """
SELECT
  dynpoi_class.source AS source,
  dynpoi_class.class AS class,
  dynpoi_class.item AS item,
  (CASE WHEN dynpoi_item.menu_%s IS NOT NULL
        THEN dynpoi_item.menu_%s
        ELSE dynpoi_item.menu_%s
   END) AS menu,
  (CASE WHEN dynpoi_class.title_%s IS NOT NULL
        THEN dynpoi_class.title_%s
        ELSE dynpoi_class.title_%s
   END) AS title,
  %s AS count,
  dynpoi_source.comment AS source_comment
FROM dynpoi_class
  LEFT JOIN dynpoi_item
    ON dynpoi_class.item = dynpoi_item.item
  LEFT JOIN dynpoi_source
    ON dynpoi_class.source = dynpoi_source.source
  %s %s
WHERE 1=1
  %s
GROUP BY
  dynpoi_class.source,
  dynpoi_class.class,
  dynpoi_class.item,
  menu,
  title,
  dynpoi_source.comment
ORDER BY
  dynpoi_class.item,
  dynpoi_class.source
"""

if show_all:
    opt_left_join = "LEFT"
else:
    opt_left_join = ""

if gen == "info":
    opt_count = "count(dynpoi_marker.source)"
    opt_join = """JOIN dynpoi_marker
    ON dynpoi_class.source = dynpoi_marker.source
    AND dynpoi_class.class = dynpoi_marker.class
"""
elif gen == "false-positive":
    opt_count = "count(dynpoi_status.source)"
    opt_join = """JOIN dynpoi_status
    ON dynpoi_class.source = dynpoi_status.source
    AND dynpoi_class.class = dynpoi_status.class
    AND dynpoi_status.status = 'false'
"""
elif gen == "done":
    opt_count = "count(dynpoi_status.source)"
    opt_join = """JOIN dynpoi_status
    ON dynpoi_class.source = dynpoi_status.source
    AND dynpoi_class.class = dynpoi_status.class
    AND dynpoi_status.status = 'done'
"""

opt_where = ""

if source <> None:
    opt_where += " AND dynpoi_class.source = %d" % source
if class_ <> None:
    opt_where += " AND dynpoi_class.class = %d" % class_
if item <> None:
    opt_where += " AND dynpoi_class.item = %d" % item
if country <> None:
    opt_where += " AND dynpoi_source.comment LIKE '%%%s'" % ("-" + country)

if source == None and item == None and country == None:
    if show_all:
        opt_count = "-1"
        if gen == "info":
            opt_left_join = ""
            opt_join = ""

sql = sql % ((lang_cur, lang_cur, lang_def) * 2 + (opt_count, opt_left_join, opt_join, opt_where))

###########################################################################

print "<table class=\"sortable\" id =\"table_source\">"
print "<thead>"
print "<tr>"
print "  <th>#</th>"
print "  <th>source</th>"
print "  <th title=\"class\">cl</th>"
print "  <th></th>"
print "  <th class=\"sorttable_sorted\">#<span id=\"sorttable_sortfwdindtable_source\">&nbsp;▾</span></th>"
print "  <th>%s</th>" % translate.get(u"utils.info.item").encode("utf8")
print "  <th>%s</th>" % translate.get(u"utils.info.title").encode("utf8")
print "  <th>%s</th>" % translate.get(u"utils.info.count").encode("utf8")
print "</tr>"

print "</thead>"
PgCursor.execute(sql)
total = 0
odd = True
for res in PgCursor.fetchall():
    odd = not odd
    if odd:
        print "<tr class='odd'>"
    else:
        print "<tr class='even'>"

    print "<td><a href=\"?source=%d\">%d</a></td>" % ((res["source"],) * 2)
    cmt_split = res["source_comment"].split("-")
    analyse = "-".join(cmt_split[0:-1])
    country = cmt_split[-1]
    print "<td>%s-<a href=\"?country=%s\">%s</a></td>" % (analyse, country, country)
    print "<td><a href=\"?item=%d&amp;class=%d\">%d</a></td>" % (res["item"], res["class"], res["class"])
    print "<td title=\"%s\"><img src=\"/map/markers/marker-l-%d.png\" alt=\"%s\"></td>" % ((res["item"],) * 3)
    print "<td><a href=\"?item=%d\">%d</a>" % ((res["item"],) * 2)
    print "</td>"
    if res["menu"]:
        print "<td>%s</td>" % res["menu"]
    else:
        print "<td></td>"
    print "<td>%s</td>" % res["title"]
    count = res["count"]
    if count == -1:
        count = "N/A"
    else:
        total += count
    print "<td><a href=\"?source=%d&amp;item=%d&amp;class=%d\">%s</a></td>" % (res["source"], res["item"], res["class"], count)
    print "</tr>"

if total > 0:
    print "<tfoot>"
    print "<tr>"
    print "  <th colspan=\"7\">Total</th>"
    print "  <th style=\"text-align: left\">%s</th>" % total
    print "</tr>"
    print "</tfoot>"

print "</table>"
###########################################################################

if (total > 0 and total < 1000) or num_points:

    if gen == "info":
        opt_count = "count(dynpoi_marker.source)"
        opt_join = """JOIN dynpoi_marker
    ON dynpoi_class.source = dynpoi_marker.source
    AND dynpoi_class.class = dynpoi_marker.class
"""

    sql = """
SELECT
  dynpoi_class.source AS source,
  dynpoi_class.class AS class,
  dynpoi_class.item AS item,
  (CASE WHEN dynpoi_item.menu_%s IS NOT NULL
        THEN dynpoi_item.menu_%s
        ELSE dynpoi_item.menu_%s
   END) AS menu,
  (CASE WHEN dynpoi_class.title_%s IS NOT NULL
        THEN dynpoi_class.title_%s
        ELSE dynpoi_class.title_%s
   END) AS title,
  (CASE WHEN subtitle_%s IS NOT NULL
        THEN subtitle_%s
        ELSE subtitle_%s
   END) AS subtitle,
  dynpoi_source.comment AS source_comment,
  subclass,
  lat,
  lon,
  elems AS elems,
  %s AS date
FROM dynpoi_class
  LEFT JOIN dynpoi_item
    ON dynpoi_class.item = dynpoi_item.item
  LEFT JOIN dynpoi_source
    ON dynpoi_class.source = dynpoi_source.source
  %s
WHERE 1=1 
  %s
ORDER BY
  %s
  dynpoi_class.item,
  dynpoi_class.source
"""

    if gen == "info":
        opt_date = "-1"
        opt_order = "subtitle,"
    elif gen in ("false-positive", "done"):
        opt_date = "date"
        opt_order = "dynpoi_status.date DESC,"
    if num_points:
        sql += "LIMIT %d" % num_points

    sql = sql % ((lang_cur, lang_cur, lang_def) * 3 + (opt_date, opt_join, opt_where, opt_order))

    print "<br>"

    print "<table class=\"sortable\">"
    print "<thead>"
    print "<tr>"
    print "  <th title=\"source\">src</th>"
    print "  <th title=\"class\">cl</th>"
    print "  <th title=\"subclass\">s</th>"
    print "  <th></th>"
    print "  <th>#</th>"
    print "  <th>item</th>"
    print "  <th title=\"position\">pos</th>"
    print "  <th>elems</th>"
    if opt_date != "-1":
        print "  <th>%s</th>" % translate.get(u"utils.info.subtitle").encode("utf8")
    else:
        print "  <th class=\"sorttable_sorted\">%s<span id=\"sorttable_sortfwdind\">&nbsp;▾</span></th>" % translate.get(u"utils.info.subtitle").encode("utf8")
    if opt_date != "-1":
        print "  <th class=\"sorttable_sorted\">date<span id=\"sorttable_sortfwdind\">&nbsp;▾</span></th>"
    print "</tr>"
    print "</thead>"
    PgCursor.execute(sql)
    odd = True
    for res in PgCursor.fetchall():
        odd = not odd
        if odd:
            print "<tr class='odd'>"
        else:
            print "<tr class='even'>"
        print "<td title=\"%(cmt)s\"><a href=\"?source=%(src)d\">%(src)d</a> </td>" % {"cmt": res["source_comment"], "src": res["source"]}
        print "<td>%d</td>" % res["class"]
        print "<td>%d</td>" % res["subclass"]
        print "<td title=\"%(item)d\"><img src=\"/map/markers/marker-l-%(item)d.png\" alt=\"%(item)d\"></td>" % {"item": res["item"]}
        print "<td><a href=\"?item=%d\">%d</a> </td>"%(res["item"],res["item"])
        if res[3]:
            print "<td title=\"%s\">%s</td>" % (res["title"], res["menu"])
        else:
            print "<td></td>"

        if res["lat"] and res["lon"]:
            lat = res["lat"] / 1000000.
            lon = res["lon"] / 1000000.
            print "<td><a href='/map/?zoom=13&amp;lat=%f&amp;lon=%f&amp;item=%d'>%.2f&nbsp;%.2f</a></td>" % (lat, lon, res["item"], lon, lat)
        else:
            print "<td></td>"

        printed_td = False
        if res["elems"]:
            elems = res["elems"].split("_")
            for e in elems:
                m = re.match(r"([a-z]+)([0-9]+)", e)
                if m:
                    if not printed_td:
                        print "<td sorttable_customkey=\"%02d%s\">" % (ord(m.group(1)[0]), m.group(2))
                        printed_td = True
                    else:
                        print "&nbsp;"
                    cur_type = m.group(1)
                    sys.stdout.write("%s&nbsp;" % cur_type[0])
                    sys.stdout.write("<a target=\"_blank\" href=\"http://www.openstreetmap.org/browse/%s/%s\">%s</a>&nbsp;"%(m.group(1), m.group(2), m.group(2)))
                    if cur_type == "node":
                        full_str = ""
                    else:
                        full_str = "/full"
                    sys.stdout.write("&nbsp;<a title=\"josm\" href=\"http://localhost:8111/import?url=http://www.openstreetmap.org/api/0.6/%s/%s%s\" target=\"hiddenIframe\">(j)</a>" % (m.group(1), m.group(2), full_str))

        if not printed_td:
            minlat = lat - 0.002
            maxlat = lat + 0.002
            minlon = lon - 0.002
            maxlon = lon + 0.002
            print "<td>"
            print "<a href=\"http://localhost:8111/load_and_zoom?left=%f&bottom=%f&right=%f&top=%f"%(minlon,minlat,maxlon,maxlat) + "\">josm</a>"

        print "</td>"
        if res["subtitle"]:
            print "<td>%s</td>" % res["subtitle"]
        elif res["title"]:
            print "<td>%s</td>" % res["title"]
        else:
            print "<td></td>"
        if opt_date != "-1":
            date = str(res["date"])
            print "<td>%s&nbsp;%s</td>" % (date[:10], date[11:16])
        print "</tr>"
    print "</table>"

    if num_points and total > num_points:
        import urlparse, urllib
        query_dict = urlparse.parse_qs(query)
        query_dict["points"] = 5 * num_points
        print "<br>"
        print "<a href='?%s'>Afficher plus d'erreurs</a>" % urllib.urlencode(query_dict, True)

else:
    print "<br>"
    print "<a href='?%s'>Afficher quelques erreurs</a>" % (query + "&amp;points=100")

###########################################################################
utils.print_tail()