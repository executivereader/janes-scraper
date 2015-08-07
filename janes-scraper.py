import mechanize
import cookielib
from BeautifulSoup import BeautifulSoup
import html2text
import re
from update_replica_set import start_mongo_client

# Browser
br = mechanize.Browser()

# Cookie Jar
cj = cookielib.LWPCookieJar()
br.set_cookiejar(cj)

# Browser options
br.set_handle_equiv(True)
br.set_handle_gzip(True)
br.set_handle_redirect(True)
br.set_handle_referer(True)
br.set_handle_robots(False)
br.set_handle_refresh(mechanize._http.HTTPRefreshProcessor(), max_time=1)

br.addheaders = [('User-agent', 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.0.1) Gecko/2008071615 Fedora/3.0.1-1.fc9 Firefox/3.0.1')]

feed = br.open('https://feeds.ihsenergy.com/Feeds.svc/ShowFeed/qVegTNGWMs')
response = feed.read()
to_scrape = re.findall("https://janes.ihs.com/CustomPages/Janes/JTICOnlineDisplayPage.aspx\\?Category=JTICONLINEEVENTS&amp;ItemId=([0-9]+)&", response)

client = start_mongo_client()

firstone = True
for event_num in to_scrape: 
    if firstone:
        # The site we will navigate into, handling its session   
        br.open('https://janes.ihs.com/CustomPages/Janes/JTICOnlineDisplayPage.aspx?Category=JTICONLINEEVENTS&ItemId=' + str(event_num) + '&ProviderName=JanesJTIC_OnlineSQLProvider&callingAppl=Feed')
        # the page above puts you on a no-javascript landing page, click to proceed
        br.select_form(nr=0)
        response = br.submit()
        #this has to be done twice for some reason
        br.select_form(nr=0)
        response = br.submit()
        
        # View available forms
        #for f in br.forms():
        #    print f
        
        # Select the first (index zero) form (the first form is a search query box)
        br.select_form(nr=0)
        
        # User credentials
        janes_credentials = client.credentials.janes.find_one()
        br.form['ctl00$ctl00$cphMainContent$cphMainSectionContent$txtUsername'] = janes_credentials['username']
        br.form['ctl00$ctl00$cphMainContent$cphMainSectionContent$txtPassword'] = janes_credentials['password']
        
        # Login
        response = br.submit()
        response.read()
        
        #now do that no-javascript skip thing again
        br.select_form(nr=0)
        response = br.submit()
        br.select_form(nr=0)
        response = br.submit()
    
    if not firstone:
        response = br.open('https://janes.ihs.com/CustomPages/Janes/JTICOnlineDisplayPage.aspx?Category=JTICONLINEEVENTS&ItemId=' + str(event_num) + '&ProviderName=JanesJTIC_OnlineSQLProvider&callingAppl=Feed')
    
    firstone = False
    
    #now we actually have the event
    event = response.read().decode("utf-8")
    event = event.replace("&nbsp;"," ").replace("n/a"," ").replace(u"\u2018", "'").replace(u"\u2019", "'")
    
    #print event
    
    event_json = {}

    event_json['url'] = 'https://janes.ihs.com/CustomPages/Janes/JTICOnlineDisplayPage.aspx?Category=JTICONLINEEVENTS&ItemId=' + str(event_num) + '&ProviderName=JanesJTIC_OnlineSQLProvider&callingAppl=Feed'
    
    event_json['event_num'] = event_num
    
    headline = re.findall("<span class='headline' >(.+?)</span",event)
    if len(headline) > 0:
        event_json['headline'] = headline[0].strip()
    description = re.findall("<span class='description' >(.+?)</span",event)
    if len(description) > 0:
        event_json['description'] = description[0].strip()
    event_type = re.findall("Event Type: </td><td>(.+?)</td",event)
    if len(event_type) > 0:
        event_json['event_type'] = event_type[0].strip()
    event_medium = re.findall("Event Medium: </td><td>(.+?)</td",event)
    if len(event_medium) > 0:
        event_json['event_medium'] = event_medium[0].strip()
    event_source = re.findall("Event Source: </td><td>(.+?)</td",event)
    if len(event_source) > 0:
        event_json['event_source'] = event_source[0].strip()
    event_date = re.findall("Event Date: </td><td>(.+?)</td",event)
    if len(event_date) > 0:
        event_json['event_date'] = event_date[0].strip()
    province = re.findall("Province: </td><td>(.+?)</td",event)
    if len(province) > 0:
        event_json['province'] = province[0].strip()
    country = re.findall("Country: </td><td>(.+?)</td",event)
    if len(country) > 0:
        event_json['country'] = country[0].strip()
    region = re.findall("Region: </td><td>(.+?)</td",event)
    if len(region) > 0:
        event_json['region'] = region[0].strip()
    
    actorstext = re.findall("<span class='Heading'>Event Actors:</span><br/><table class='detailsTable' ><tr  class='detailsTableHeaderRow'><td class='HeaderCell' >Role</td><td class='HeaderCell' >Name</td><td class='HeaderCell' >Group Name</td><td class='HeaderCell' >Place</td><td class='HeaderCell' >Scope</td><td class='HeaderCell' >Region</td><td class='HeaderCell' >Orientation</td><td class='HeaderCell' >Type</td></tr>(.+?)</table><br/>",event)[0]
    actors = re.findall("<tr><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td></tr>",actorstext)
    actors_json = []
    for actor in actors:
        role = actor[0].strip()
        name = actor[1].strip()
        group_name = actor[2].strip()
        place = actor[3].strip()
        scope = actor[4].strip()
        region = actor[5].strip()
        orientation = actor[6].strip()
        actor_type = actor[7].strip()
        actors_json.append({"role":role,"name":name,"group_name":group_name,"place":place,"scope":scope,"region":region,"orientation":orientation,"actor_type":actor_type})
    
    event_json['actors'] = actors_json
    
    attack_scale = re.findall("Attack Scale: </td><td>(.+?)</td",event)
    if len(attack_scale) > 0:
        event_json['attack_scale'] = attack_scale[0].strip()
    attack_environment = re.findall("Attack Environment: </td><td>(.+?)</td",event)
    if len(attack_environment) > 0:
        event_json['attack_environment'] = attack_environment[0].strip()
    attack_tactic = re.findall("Attack Tactic: </td><td>(.+?)</td",event)
    if len(attack_tactic) > 0:
        event_json['attack_tactic'] = attack_tactic[0].strip()
    
    targetstext = re.findall("<span class='Heading'>Attack Target:</span><br/><table  class='detailsTable'><tr class='detailsTableHeaderRow'><td class='HeaderCell' >Sector</td><td class='HeaderCell' >Sub Sector</td><td class='HeaderCell' >Objects</td><td class='HeaderCell' >Nations</td></tr>(.+?)</table><br/>",event)
    if len(targetstext) > 0:
        targets = re.findall("<tr><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td></tr>",targetstext[0])
        targets_json = []
        for target in targets:
            sector = target[0].strip()
            subsector = target[1].strip()
            objects = target[2].strip()
            nations = target[3].strip()
            targets_json.append({"sector": sector,"subsector": subsector,"objects": objects,"nations": nations})
        event_json['targets'] = targets_json
        
    attackmodestext = re.findall("<span class='Heading'>Attack Mode:</span><br/><table class='detailsTable'><tr class='detailsTableHeaderRow'><td class='HeaderCell'>Platform</td><td class='HeaderCell'>Weapon</td><td class='HeaderCell'>Device Count</td><td class='HeaderCell'>Suicide Attack</td></tr>(.+?)</table><br/>",event)
    if len(attackmodestext) > 0:
        attackmodes = re.findall("<tr><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td></tr>",attackmodestext[0])
        attackmodes_json = []
        for attackmode in attackmodes:
            platform = attackmode[0].strip()
            weapon = attackmode[1].strip()
            device_count = attackmode[2].strip()
            suicide = attackmode[3].strip()
            attackmodes_json.append({"platform":platform,"weapon":weapon,"device_count":device_count,"suicide":suicide})
        event_json['attackmodes'] = attackmodes_json
    
    casualtiestext = re.findall("<span class='Heading'>Casualties</span><br/><table class='detailsTable'  ><tr class='detailsTableHeaderRow'><td class='HeaderCell' >Type</td><td class='HeaderCell' >Militant</td><td class='HeaderCell' >Security Force</td><td class='HeaderCell' >Civillian</td><td class='HeaderCell' >Civillian/SF</td><td class='HeaderCell' >Unidentified</td><td class='HeaderCell' >Non-Militant</td><td>Total</td></tr>(.+?)</table><br/>",event)
    if len(casualtiestext) > 0:
        casualtieslines = re.findall("<tr><td\\s+class='HeaderCell' >(.*?)</td><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td></tr>",casualtiestext[0])
        casualties_json = []
        for casualtiesline in casualtieslines:
            casualtiesline_type = casualtiesline[0].strip()
            casualtiesline_militant = casualtiesline[1].strip()
            casualtiesline_securityforces = casualtiesline[2].strip()
            casualtiesline_civilian = casualtiesline[3].strip()
            casualtiesline_civiliansf = casualtiesline[4].strip()
            casualtiesline_unidentified = casualtiesline[5].strip()
            casualtiesline_nonmilitant = casualtiesline[6].strip()
            casualtiesline_total = casualtiesline[7].strip()
            casualties_json.append({"type":casualtiesline_type,"militant":casualtiesline_militant,"securityforces":casualtiesline_securityforces,"civilian":casualtiesline_civilian,"civiliansf":casualtiesline_civiliansf,"unidentified":casualtiesline_unidentified,"nonmilitant":casualtiesline_nonmilitant,"total":casualtiesline_total})
        event_json['casualties'] = casualties_json
    
    statement_type = re.findall("<span class='Heading'>CT Statement:</span><br/><table  class='detailsTable'><tr><td class='HeaderCell' >Type: </td><td>(.*?)</td></tr></table><br/>",event)
    if len(statement_type) > 0:
        event_json['statement_type'] = statement_type[0].strip()
    
    ctoptext = re.findall("<span class='Heading'>CT Operation Details:</span><br/><table  class='detailsTable'>(.*?)</table>",event)
    if len(ctoptext) > 0:
        ctoptable = re.findall("<tr><td class='HeaderCell'>Environment:</td><td>(.*?)</td></tr><tr><td class='HeaderCell'>Type:</td><td>(.*?)</td></tr><tr><td style='vertical-align:top;' class='HeaderCell'>Force:</td><td>(.*?)</td></tr><tr><td class='HeaderCell'>Assets:</td><td>(.*?)</td></tr><tr><td class='HeaderCell'>Arms Seized/Destroyed:</td><td>(.*?)</td",ctoptext[0])
        if len(ctoptable) > 0:
            ctoptable = ctoptable[0]
            #print ctoptable
            ctop_environments = re.findall("(^.*?)<|>(.*?)<|>(.*?$)|(^[A-z 0-9]*$)",ctoptable[0].strip())
            event_json['ct_environments'] = [item for sublist in ctop_environments for item in sublist if item != '']
            ctop_types = re.findall("(^.*?)<|>(.*?)<|>(.*?$)|(^[A-z 0-9]*$)",ctoptable[1].strip())
            event_json['ct_types'] = [item for sublist in ctop_types for item in sublist if item != '']
            ctop_forces = re.findall("(^.*?)<|>(.*?)<|>(.*?$)|(^[A-z 0-9]*$)",ctoptable[2].strip())
            event_json['ct_forces'] = [item for sublist in ctop_forces for item in sublist if item != '']
            ctop_assets = re.findall("(^.*?)<|>(.*?)<|>(.*?$)|(^[A-z 0-9]*$)",ctoptable[3].strip())
            event_json['ct_assets'] = [item for sublist in ctop_assets for item in sublist if item != '']
            ctop_arms = re.findall("(^.*?)<|>(.*?)<|>(.*?$)|(^[A-z 0-9]*$)",ctoptable[4].strip())
            event_json['ct_armsseized'] = [item for sublist in ctop_arms for item in sublist if item != '']
    print event_json
    try:
        client.janes.events.insert(event_json)
    except:
        pass
