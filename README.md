# Command Line Blogging Client
This application allows you to edit/post entries on a blog via
XML-RPC calls. For more information about this script, visit:

* [GitHub repo](https://github.com/keithbowes/mtsend)
* [Scott Yang's original site](https://scott.yang.id.au/2002/12/mtsendpy/)


## REQUIREMENTS
mtsend.py requires [Python](http://python.org).  The master branch requires
Python 3.0 or higher.  The python-2.7 branch has most fixes and new features
backported and can run in Python 2.7.x.  The python-2.4 branch contains [Scott
Yang](https://github.com/scottyang)'s original version 1.1 and should work in
versions of Python from 2.4 to 2.6.x (and perhaps older versions of Python
2.x), but doesn't contain the improvements of the master and python-2.7
branches (mostly because I don't want to install ancient versions of Python to
test them; as of writing, Python 2.7.x is the most used version of Python, and
older versions are dwindling).


## CONFIGURATION FILE
Configuration file for mtsend.py is in the style of Windows INI files, which
consist of sections and key/value pairs. There are 3 main sections - global,
site and blog. The configuration file should be mode 600.

Global Section:
  There is only one key/value in this section, and it is used to note the
  default blog alias to use if it is not provided on the command line.
  For example:

<pre>
    [global]
    default=example
</pre>

  It shows the default blog alias will be 'example'

Site Section:
  You can have multiple site sections for each blog installation
  you have access to. The section name will be [site-"site name"]. For
  example:
    
<pre>
    [site-test]
    url=http://testdomain.com/xmlrpc.php
    username=foo
    password=bar
    encoding=ISO-8859-1
</pre>

  It defines site "test" with the URL to your site's XML-RPC script, and the
  username/password used to access that site. "encoding" is optional, and
  defaults to ISO-8859-1.

Blog Section:
  You can have multiple blog sections for each blog you have on the sites you
  have access to. Blogs are distinguished by their 'alias', which you can
  select in the command line using -a. The section name for this blog will be
  [blog-"blog alias"]. For example,

<pre>
    [blog-example]
    site=test
    blogid=3
</pre>

  Each blog section must have "site", which indicates the site this blog
  belongs to, so that mtsend would be able to locate site-related
  information from the configuration file. It also needs the blog ID on that
  site. To find out all the blog IDs, you can use -B "site name" to print
  out the list.


## POST FORMAT
When editing or posting via mtsend, the post needs to be in a specific format.
The format is very close to [Movable Type's import/export
format](http://movabletype.org/documentation/appendices/import-export-format.htm).

It consists of a header and body. For example:

  <var>header1</var>: <var>value1</var><br />
  <var>header2</var>: <var>value2</var><br />
  <var>header3</var>: <var>value3</var><br />
  \-\-\-\-\-<br />
  BODY:<br />
  \..\..<br />
  \-\-\-\-\-<br />
  EXTENDED BODY:<br />
  \..\..<br />
  \-\-\-\-\-<br />
  EXCERPT:<br />
  \..\..<br />

Extended body and excerpt are optional in a post. Most header elements are
optional when you are creating a new post. If they do not provide a value,
then the default value configured by your blog will be used.

These are the header keys/values:

Key                 | Value                           | Description
-------------- ---- | ------------------------------- | -----------
TITLE               |                                 | The title of this post.
ALLOW&nbsp;COMMENTS | 0/1                             | Whether this post allows comments.
ALLOW&nbsp;PINGS    | 0/1                             | Whether this post allows trackback pings.
CATEGORY            |                                 | The category associated with this post entry. You can have multiple CATEGORY in the header. The first CATEGORY automatically becomes the primary category, if PRIMARY CATEGORY is not specified.
CONVERT&nbsp;BREAKS | 0/1/customised text filter name | Whether the line break will be automatically converted into &lt;br/&gt; and &lt;p/&gt; when posted. It can also be the name of an installed text filter. To get the list of installed text filter, use mtsend.py -T.
DATE                | dd/mm/yyyy HH:MM:SS [AM\|PM]    | The post date. It might not work if you are creating a new post.
KEYWORDS            |                                 | The keywords of your post.
PING                |                                 | The URL to be pinged during posting. You can have multiple PING in the header.


## COMMAND LINE ARGUMENTS
Invoke <kbd>python2 \-- mtsend.py</kbd> to see a list of arguments.


## HISTORY

### 1.2 - TBD
+ Started my own fork (keithbowes@github)
+ Ported to Python 3
+ Support for the XDG directory layout
+ Fixed proxy support
+ Added new functionality:
   * Listing posts
   * Deleting posts
   * Adding comments
   * Deleting comments
   * Seeing the true post status

### 1.1 - 19 Nov 2005
+ Add SSL support for proxy.

### [1.0](http://scott.yang.id.au/2005/05/update-mtsendpy-10-has-been-released.html) - 20 May 2005
+ `time` module related fix for Python 2.4.
+ Ensure all cells passed to print_table() function are in string-type.

### 0.6.1 - 6 Apr 2004
+ Properly handles mt\_allow\_comments for MT2.6 servers.

### [0.6](http://scott.yang.id.au/2004/04/update-mtsendpy-06-has-been-released.html) - 1 Apr 2004
+ Add build-in support for HTTP proxy server, which is detected via
  environment variable HTTP_PROXY.
+ Alternative encoding for XML-RPC packets.

### [0.5](http://scott.yang.id.au/2003/10/update-mtsendpy-05-has-been-released.html) - 14 Oct 2003
+ Remove the support of MT2.5. Use the [older version](http://scott.yang.id.au/2003/03/update-mtsendpy-04-has-been-released.html) of mtsend.py if you
  need these supports.
+ Support KEYWORDS and PING into the header.
+ Add new functionalities provided by MT2.6's backend.
  - List out trackback pings of a post.
  - List out text filters installed.
+ Documentation in the source code.

### [0.4](http://scott.yang.id.au/2003/03/update-mtsendpy-04-has-been-released.html) - 10 Mar 2003
+ Support the new metaWeblog.newMediaObject() function via mtsend.py -U
  filename, i.e. you can now upload text/binary files to your
  MovableType site via mtsend.py!
+ Use mt.getRecentPostTitles() function in MT2.6 to save bandwidth.
+ Some bug fixes due to some inconsistency between MT2.6 and MT2.5.

### 0.3 - 3 Jan 2003
+ Make it to work on Python 2.1. "xmlrpclib" needs to be downloaded
  separately. It is tested
  on Python 2.1.2 for Windows.
  
### 0.2 - 30 Dec 2002
+ Fixed a bug in saving the post entry back, where new line characters
  are stripped.

### 0.1 - 30 Dec 2002
+ Initial public version
