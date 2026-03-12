#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import sys
import time
from decimal import Decimal

from ikabot import config
from ikabot.config import materials_names
from ikabot.helpers.botComm import checkTelegramData, sendToBot
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import banner, enter
from ikabot.helpers.pedirInfo import getIdsOfCities, read
from ikabot.helpers.varios import addThousandSeparator, daysHoursMinutes


def _format_resources(resources, storage, free_space):
    icons = ["🪵", "🍷", "🪨", "🔮", "🧨"]
    parts = []
    for i in range(len(materials_names)):
        parts.append(
            "{} {} / {} ({})".format(
                icons[i],
                addThousandSeparator(resources[i]),
                addThousandSeparator(storage),
                addThousandSeparator(free_space[i]),
            )
        )
    return " | ".join(parts)


def _format_resources_short(resources):
    icons = ["🪵", "🍷", "🪨", "🔮", "🧨"]
    parts = []
    for i in range(len(materials_names)):
        parts.append("{} {}".format(icons[i], addThousandSeparator(resources[i])))
    return " | ".join(parts)


def _wrap_items(items, max_len=140):
    lines = []
    current = ""
    for item in items:
        if not current:
            current = item
            continue
        if len(current) + 3 + len(item) > max_len:
            lines.append(current)
            current = item
        else:
            current = current + " | " + item
    if current:
        lines.append(current)
    return lines


def _split_messages(sections, max_len=3500):
    messages = []
    current = ""
    for section in sections:
        if not current:
            current = section
            continue
        if len(current) + 2 + len(section) > max_len:
            messages.append(current)
            current = section
        else:
            current = current + "\n\n" + section
    if current:
        messages.append(current)
    return messages


def telegramAccountReport(session, event, stdin_fd, predetermined_input):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd: int
    predetermined_input : multiprocessing.managers.SyncManager.list
    """
    sys.stdin = os.fdopen(stdin_fd)
    config.predetermined_input = predetermined_input
    try:
        banner()
        if checkTelegramData(session) is False:
            event.set()
            return

        print("Generating Telegram account snapshot...")
        print("Choose report version:")
        print("(1) Detailed")
        print("(2) Summary")
        choice = read(min=1, max=2, digit=True, default=1)
        detailed = choice == 1

        (ids, __) = getIdsOfCities(session)
        total_resources = [0] * len(materials_names)
        total_production = [0] * len(materials_names)
        total_wine_consumption = 0
        total_housing_space = 0
        total_citizens = 0
        available_ships = 0
        total_ships = 0
        total_gold = 0
        total_gold_production = 0

        city_sections = []

        for city_id in ids:
            html = session.get("view=city&cityId={}".format(city_id), noIndex=True)
            city = getCity(html)

            data = session.get("view=updateGlobalData&ajax=1", noIndex=True)
            json_data = json.loads(data, strict=False)[0][1]["headerData"]
            if json_data["relatedCity"]["owncity"] != 1:
                continue

            wood_per_hour = int(Decimal(json_data["resourceProduction"]) * 3600)
            good_per_hour = int(Decimal(json_data["tradegoodProduction"]) * 3600)
            type_good = int(json_data["producedTradegood"])

            total_production[0] += wood_per_hour
            total_production[type_good] += good_per_hour
            total_wine_consumption += int(json_data["wineSpendings"])

            total_housing_space += int(json_data["currentResources"]["population"])
            total_citizens += int(json_data["currentResources"]["citizens"])

            total_resources[0] += int(json_data["currentResources"]["resource"])
            total_resources[1] += int(json_data["currentResources"]["1"])
            total_resources[2] += int(json_data["currentResources"]["2"])
            total_resources[3] += int(json_data["currentResources"]["3"])
            total_resources[4] += int(json_data["currentResources"]["4"])

            available_ships = int(json_data["freeTransporters"])
            total_ships = int(json_data["maxTransporters"])
            total_gold = int(Decimal(json_data["gold"]))
            total_gold_production = int(
                Decimal(
                    json_data["scientistsUpkeep"]
                    + json_data["income"]
                    + json_data["upkeep"]
                )
            )

            city_lines = []
            city_header = "🏛️ {} [{}:{}]".format(
                city["cityName"], city["x"], city["y"]
            )
            if city.get("isCapital"):
                city_header += " ★"
            city_lines.append(city_header)

            city_lines.append(
                "📦 Storage: {}".format(addThousandSeparator(city["storageCapacity"]))
            )
            city_lines.append(
                "📦 Resources: {}".format(
                    _format_resources(
                        city["availableResources"],
                        city["storageCapacity"],
                        city["freeSpaceForResources"],
                    )
                )
            )
            if detailed and sum(city["resourcesListedForSale"]) > 0:
                city_lines.append(
                    "🏪 On sale: {}".format(
                        _format_resources_short(city["resourcesListedForSale"])
                    )
                )

            city_lines.append(
                "⚙️ Production/h: 🪵 {} | {} {}".format(
                    addThousandSeparator(wood_per_hour),
                    ["", "🍷", "🪨", "🔮", "🧨"][type_good],
                    addThousandSeparator(good_per_hour),
                )
            )

            total_city_citizens = int(json_data["currentResources"]["citizens"])
            total_city_housing = int(json_data["currentResources"]["population"])
            city_lines.append(
                "👥 Citizens: {} / {} | free: {}".format(
                    addThousandSeparator(total_city_citizens),
                    addThousandSeparator(total_city_housing),
                    addThousandSeparator(city["freeCitizens"]),
                )
            )

            if detailed:
                consumption_per_hour = int(city["wineConsumptionPerHour"])
                if consumption_per_hour == 0:
                    wine_time = "∞"
                elif type_good == 1 and good_per_hour >= consumption_per_hour:
                    wine_time = "∞"
                else:
                    consumption_per_second = Decimal(consumption_per_hour) / Decimal(3600)
                    remaining_seconds = Decimal(city["availableResources"][1]) / Decimal(
                        consumption_per_second
                    )
                    wine_time = daysHoursMinutes(remaining_seconds)
                city_lines.append(
                    "🍷 Wine use/h: {} | ⏳ Wine left: {}".format(
                        addThousandSeparator(consumption_per_hour), wine_time
                    )
                )

            if detailed:
                building_items = []
                for building in city["position"]:
                    if building["name"] == "empty":
                        continue
                    level = building.get("level")
                    if level is None:
                        continue
                    suffix = ""
                    if building.get("isBusy"):
                        suffix += "+"
                    if building.get("isMaxLevel"):
                        suffix += "✓"
                    elif building.get("canUpgrade"):
                        suffix += "↑"
                    building_items.append(
                        "{} {}{}".format(building["name"], level, suffix)
                    )
                if building_items:
                    city_lines.append("🏗️ Buildings:")
                    for line in _wrap_items(building_items):
                        city_lines.append(line)

            city_sections.append("\n".join(city_lines))

        header = "📊 IKABOT | {} | s{}-{} | {}".format(
            session.username,
            session.mundo,
            session.servidor,
            time.strftime("%Y-%m-%d %H:%M:%S"),
        )
        summary = [
            "🧾 GENERAL SUMMARY",
            "🛳️ Ships: {}/{}".format(
                addThousandSeparator(available_ships),
                addThousandSeparator(total_ships),
            ),
            "💰 Gold: {} | 💹 Gold/h: {}".format(
                addThousandSeparator(total_gold),
                addThousandSeparator(total_gold_production),
            ),
            "👥 Citizens: {} / {}".format(
                addThousandSeparator(total_citizens),
                addThousandSeparator(total_housing_space),
            ),
            "🍷 Total wine use/h: {}".format(
                addThousandSeparator(total_wine_consumption)
            ),
            "📦 Total resources: {}".format(_format_resources_short(total_resources)),
            "⚙️ Total production/h: 🪵 {} | 🍷 {} | 🪨 {} | 🔮 {} | 🧨 {}".format(
                addThousandSeparator(total_production[0]),
                addThousandSeparator(total_production[1]),
                addThousandSeparator(total_production[2]),
                addThousandSeparator(total_production[3]),
                addThousandSeparator(total_production[4]),
            ),
        ]

        separator = "----------"
        sections = [header, separator, "\n".join(summary)]
        for city_section in city_sections:
            sections.append(separator)
            sections.append(city_section)

        messages = _split_messages(sections, max_len=3500)
        for msg in messages:
            sendToBot(session, msg, Token=True)

        print("Sent {} Telegram message(s).".format(len(messages)))
        enter()
        event.set()
    except KeyboardInterrupt:
        event.set()
