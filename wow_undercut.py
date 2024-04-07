#!/usr/bin/python3
from __future__ import print_function
import os, json, time
from datetime import datetime
import requests

print("Sleep 10 sec on start to avoid spamming the api")
time.sleep(10)

#### GLOBALS ####
alert_record = []
undercut_alert_data = json.load(open("wow_user_data/undercut/region_undercut.json"))
if len(undercut_alert_data) == 0:
    print(
        "Error please generate your undercut data from our addon: https://www.curseforge.com/wow/addons/saddlebag-exchange"
    )
    print("Then paste it into user_data/simple/region_undercut.json")
    exit(1)
region = undercut_alert_data["region"]

try:
    webhook_url = json.load(open("wow_user_data/config/undercut/webhooks.json"))[
        "webhook"
    ]
except FileNotFoundError:
    print(
        "Error: No webhook file found for undercut, add your webhook to wow_user_data/config/undercut/webhooks.json"
    )
    exit(1)
except KeyError:
    print(
        "Error: No webhook found in wow_user_data/config/undercut/webhooks.json add one in"
    )
    exit(1)


def simple_undercut(json_data):
    snipe_results = requests.post(
        "http://api.saddlebagexchange.com/api/wow/regionundercut",
        json=json_data,
    ).json()

    return snipe_results


def get_update_timers(region, simple_undercut=False):
    print("Getting update timers")
    # get from api every time
    update_timers = requests.post(
        "http://api.saddlebagexchange.com/api/wow/uploadtimers",
        json={},
    ).json()["data"]

    # cover specific realms
    if simple_undercut:
        if region == "EU":
            update_id = -2
        else:
            update_id = -1
        server_update_times = [
            time_data
            for time_data in update_timers
            if time_data["dataSetID"] == update_id
        ]
    else:
        server_update_times = [
            time_data
            for time_data in update_timers
            if time_data["dataSetID"] not in [-1, -2] and time_data["region"] == region
        ]
        print(server_update_times)

    return server_update_times


def send_to_discord(embed, webhook_url):
    # Send message
    print(f"sending embed to discord...")
    req = requests.post(webhook_url, json={"embeds": [embed]})
    if req.status_code != 204 and req.status_code != 200:
        print(f"Failed to send embed to discord: {req.status_code} - {req.text}")
    else:
        print(f"Embed sent successfully")


def create_embed(title, description, fields, color="red"):
    if color == "red":
        embed_color = 0xFF0000
    elif color == "green":
        embed_color = 0x00FF00
    else:
        embed_color = 0x7289DA
    embed = {
        "title": title,
        "description": description,
        "color": embed_color,  # Blurple color code
        "fields": fields,
        "footer": {
            "text": time.strftime(
                "%m/%d/%Y %I:%M %p", time.localtime()
            )  # Adds current time as footer
        },
    }
    return embed


def format_discord_message():
    global alert_record
    raw_undercut_data = simple_undercut(undercut_alert_data)
    if not raw_undercut_data:
        send_discord_message(
            f"An error occured got empty response {raw_undercut_data}", webhook_url
        )
        return
    for realm, json_data in raw_undercut_data["results_by_realm"].items():
        embed_uc = []
        embed_nf = []

        for dataset in ["undercuts", "not_found"]:
            for value in json_data[dataset]:
                # logger.info(value)

                item_name = value.pop("item_name")
                item_id = value.pop("item_id")
                link = value.pop("link")
                desc = (
                    f"[Link]({link})\nItem ID: ({item_id})\n"
                    + f"Lowest Price: {value['lowest_price']}\nYour Price: {value['user_price']}"
                )

                if dataset == "undercuts":
                    embed_uc.append(
                        {"name": f"**{item_name}**", "value": desc, "inline": True}
                    )
                else:
                    embed_nf.append(
                        {"name": f"**{item_name}**", "value": desc, "inline": True}
                    )

        # send message for each realm
        if len(embed_uc) > 0:
            embed = create_embed(
                "Undercuts",
                f"List of your items that are undercut!\nRealm: {realm}\nRegion: {region}\n",
                embed_uc,
                "red",
            )
            send_to_discord(embed, webhook_url)

        if len(embed_nf) > 0:
            embed = create_embed(
                "Sold, Expired or Not Found",
                f"List of items with price levels not found in the blizzard api data.\nRealm: {realm}\nRegion: {region}\n",
                embed_nf,
                "green",
            )
            send_to_discord(embed, webhook_url)


#### MAIN ####
def main():
    global alert_record
    update_time = get_update_timers(region, True)[0]["lastUploadMinute"]
    while True:
        current_min = int(datetime.now().minute)

        # clear out the alert record once an hour
        if current_min == 0:
            print("\n\nClearing Alert Record\n\n")
            alert_record = []

        # # update the update min once per hour
        # if current_min == 1:
        #     update_time = get_update_timers(region, True)[0]["lastUploadMinute"]

        # check the upload min up 3 to 5 min after the commodities trigger
        if update_time + 3 <= current_min <= update_time + 5:
            print(
                f"NOW AT MATCHING UPDATE MIN!!! {datetime.now()}, checking for undercuts"
            )
            format_discord_message()
            time.sleep(60)
        else:
            print(
                f"at {datetime.now()}, waiting for {[update_time]} to check undercuts"
            )
            time.sleep(60)


def send_discord_message(message, webhook_url):
    try:
        json_data = {"content": message}
        response = requests.post(webhook_url, json=json_data)
        response.raise_for_status()  # Raise an exception for non-2xx status codes
        return True  # Message sent successfully
    except requests.exceptions.RequestException as ex:
        print("Error sending Discord message: %s", ex)
        return False  # Failed to send the message


if not send_discord_message("starting simple undercuts", webhook_url):
    print("Failed to send Discord message")
    exit(1)
else:
    print("Discord message sent successfully")

if __name__ == "__main__":
    # run once on start
    format_discord_message()
    # run on schedule
    main()
