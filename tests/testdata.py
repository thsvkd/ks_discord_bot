from ks_bot.common.dataclass import *
from ks_bot.common.common import *


class TestData_Player:
    EXAMPLE_PLAYER1_1 = Player(
        id='account.1ed1250b36304678ae706a0c5fa18f64',
        normalized_id='1ed1250b36304678ae706a0c5fa18f64',
        name='example_player_name1',
        platform='steam',
        ban_type='Innocent',
        clan_id='clan.fab1814f906d49b08d77b3adb783cc24',
        match_list=[
            {"type": "match", "id": "f6a69afd-fb60-45da-8b40-a2e013db0f33"},  # 1
            {"type": "match", "id": "456ad743-389e-44e1-9da4-18fb12ea54de"},  # 2
            {"type": "match", "id": "bdae2395-0552-49bb-b543-3c3b33e758f4"},  # 3
            {"type": "match", "id": "7cbaf996-cc3f-426b-bba4-ba5920da75d0"},  # 4
            {"type": "match", "id": "4c8e3260-6cf1-47bb-9072-6ec1959c7b90"},  # 5
            {"type": "match", "id": "9b32dcb9-8389-4bb6-8f93-cd660e8c9d50"},  # 6
            {"type": "match", "id": "8fcf2fc9-dd1a-4c45-b335-a3ed611a9157"},  # 7
            {"type": "match", "id": "6dfac99a-fec5-4a5c-8c65-278f9603778a"},  # 8
            {"type": "match", "id": "6a44a362-8269-4dac-b649-3388c8203037"},  # 9
            {"type": "match", "id": "606b8967-b63a-4515-a56c-e91a4e89d5ca"},  # 10
            {"type": "match", "id": "60f84138-e79e-4f0a-8073-06cff5690f4d"},  # 11
            {"type": "match", "id": "f95eb9ef-0000-4402-b63c-e564c5f9a77a"},  # 12
            {"type": "match", "id": "e72fff5e-b77b-46a7-8506-55be545a7ff9"},  # 13
            {"type": "match", "id": "f3ec80c7-05c5-4083-95ef-66bdc32e2706"},  # 14
            {"type": "match", "id": "88cdd685-ef64-4cf6-b95d-d9e4b5813c6d"},  # 15
            {"type": "match", "id": "d2a846cf-c3d1-4aa1-8eaa-823c18676384"},  # 16
            {"type": "match", "id": "b741645f-358d-4075-bdeb-65adde059b72"},  # 17
            {"type": "match", "id": "94fe2a30-6944-48f1-aa93-110ccf41a900"},  # 18
            {"type": "match", "id": "9705ab71-a8bf-43ab-b918-f4e2941755e5"},  # 19
            {"type": "match", "id": "6f0968cc-90a3-4a94-bdfc-1a9cec30f802"},  # 20
            {"type": "match", "id": "b6ee83ca-bb02-43b6-b8cf-ca9faafa1bfa"},  # 21
            {"type": "match", "id": "69ea48ab-a9d9-45f6-9728-3fd459ea5f71"},  # 22
            {"type": "match", "id": "4b21dce8-6334-45d5-bf5e-ac00f81dadfd"},  # 23
            {"type": "match", "id": "c908bf2f-0c21-4693-b698-820a6e8b487d"},  # 24
            {"type": "match", "id": "fc084649-e184-45df-9739-7e96fb4ff28b"},  # 25
        ],
    )
    EXAMPLE_PLAYER1_2 = Player(
        id='account.1ed1250b36304678ae706a0c5fa18f64',
        normalized_id='1ed1250b36304678ae706a0c5fa18f64',
        name='example_player_name1',
        platform='steam',
        ban_type='Innocent',
        clan_id='clan.fab1814f906d49b08d77b3adb783cc24',
        match_list=[
            {"type": "match", "id": "f6a69afd-fb60-45da-8b40-a2e013db0f33"},  # 1
            {"type": "match", "id": "456ad743-389e-44e1-9da4-18fb12ea54de"},  # 2
            {"type": "match", "id": "bdae2395-0552-49bb-b543-3c3b33e758f4"},  # 3
            {"type": "match", "id": "7cbaf996-cc3f-426b-bba4-ba5920da75d0"},  # 4
            {"type": "match", "id": "4c8e3260-6cf1-47bb-9072-6ec1959c7b90"},  # 5
            {"type": "match", "id": "9b32dcb9-8389-4bb6-8f93-cd660e8c9d50"},  # 6
            {"type": "match", "id": "8fcf2fc9-dd1a-4c45-b335-a3ed611a9157"},  # 7
            {"type": "match", "id": "6dfac99a-fec5-4a5c-8c65-278f9603778a"},  # 8
            {"type": "match", "id": "6a44a362-8269-4dac-b649-3388c8203037"},  # 9
            {"type": "match", "id": "606b8967-b63a-4515-a56c-e91a4e89d5ca"},  # 10
            {"type": "match", "id": "60f84138-e79e-4f0a-8073-06cff5690f4d"},  # 11
            {"type": "match", "id": "f95eb9ef-0000-4402-b63c-e564c5f9a77a"},  # 12
            {"type": "match", "id": "e72fff5e-b77b-46a7-8506-55be545a7ff9"},  # 13
            {"type": "match", "id": "f3ec80c7-05c5-4083-95ef-66bdc32e2706"},  # 14
            {"type": "match", "id": "88cdd685-ef64-4cf6-b95d-d9e4b5813c6d"},  # 15
        ],
    )
    EXAMPLE_PLAYER1_3 = Player(
        id='account.1ed1250b36304678ae706a0c5fa18f64',
        normalized_id='1ed1250b36304678ae706a0c5fa18f64',
        name='example_player_name1',
        platform='steam',
        ban_type='Innocent',
        clan_id='clan.fab1814f906d49b08d77b3adb783cc24',
        match_list=[
            {"type": "match", "id": "f6a69afd-fb60-45da-8b40-a2e013db0f33"},  # 1
            {"type": "match", "id": "456ad743-389e-44e1-9da4-18fb12ea54de"},  # 2
            {"type": "match", "id": "bdae2395-0552-49bb-b543-3c3b33e758f4"},  # 3
            {"type": "match", "id": "7cbaf996-cc3f-426b-bba4-ba5920da75d0"},  # 4
            {"type": "match", "id": "4c8e3260-6cf1-47bb-9072-6ec1959c7b90"},  # 5
            {"type": "match", "id": "9b32dcb9-8389-4bb6-8f93-cd660e8c9d50"},  # 6
            {"type": "match", "id": "8fcf2fc9-dd1a-4c45-b335-a3ed611a9157"},  # 7
            {"type": "match", "id": "6dfac99a-fec5-4a5c-8c65-278f9603778a"},  # 8
        ],
    )
    EXAMPLE_PLAYER1_4 = Player(
        id='account.1ed1250b36304678ae706a0c5fa18f64',
        normalized_id='1ed1250b36304678ae706a0c5fa18f64',
        name='example_player_name1',
        platform='steam',
        ban_type='Innocent',
        clan_id='clan.fab1814f906d49b08d77b3adb783cc24',
        match_list=[],
    )
    EXAMPLE_PLAYER2 = Player(
        id='account.54ef79a291c846fabfbdc8b36b070ccc',
        normalized_id='54ef79a291c846fabfbdc8b36b070ccc',
        name='example_player_name2',
        platform='steam',
        ban_type='Innocent',
        clan_id='clan.fab1814f906d49b08d77b3adb783cc24',
        match_list=[],
    )
    EXAMPLE_PLAYER3 = Player(
        id='account.0826e8a2d7d44b8c93fd6b606dccdb93',
        normalized_id='0826e8a2d7d44b8c93fd6b606dccdb93',
        name='example_player_name3',
        platform='steam',
        ban_type='Innocent',
        clan_id='clan.fab1814f906d49b08d77b3adb783cc24',
        match_list=[],
    )
    EXAMPLE_PLAYER4 = Player(
        id='account.5033b58b23644c7eab7bf33781ad762a',
        normalized_id='5033b58b23644c7eab7bf33781ad762a',
        name='example_player_name4',
        platform='steam',
        ban_type='Innocent',
        clan_id='clan.fab1814f906d49b08d77b3adb783cc24',
        match_list=[],
    )


class TestData_PlayerMatchStats:
    EXAMPLE_PLAYER_MATCH_STATS1 = (
        TestData_Player.EXAMPLE_PLAYER1_4,
        PlayerMatchStats(
            player_name='example_player_name1',
            match_id='f6a69afd-fb60-45da-8b40-a2e013db0f33',
            is_custom_match=False,
            game_mode=GameMode.SQUAD,
            match_type=MatchType.NORMAL,
            DBNOs=1,
            boosts=1,
            damage_dealt=1.0,
            death_type='',
            headshot_kills=1,
            heals=1,
            win_place=1,
            kill_place=1,
            kill_streaks=1,
            kills=1,
            assists=1,
            longest_kill=1.0,
            revives=1,
            ride_distance=1.0,
            swim_distance=1.0,
            walk_distance=1.0,
            road_kills=1,
            team_kills=1,
            time_survived=1,
            vehicle_destroys=1,
            weapons_acquired=1,
        ),
    )
    EXAMPLE_PLAYER_MATCH_STATS2 = (
        TestData_Player.EXAMPLE_PLAYER1_4,
        PlayerMatchStats(
            player_name='example_player_name1',
            match_id='456ad743-389e-44e1-9da4-18fb12ea54de',
            is_custom_match=False,
            game_mode=GameMode.SQUAD,
            match_type=MatchType.NORMAL,
            DBNOs=2,
            boosts=2,
            damage_dealt=2.0,
            death_type='',
            headshot_kills=2,
            heals=2,
            win_place=2,
            kill_place=2,
            kill_streaks=2,
            kills=2,
            assists=2,
            longest_kill=2.0,
            revives=2,
            ride_distance=2.0,
            swim_distance=2.0,
            walk_distance=2.0,
            road_kills=2,
            team_kills=2,
            time_survived=2,
            vehicle_destroys=2,
            weapons_acquired=2,
        ),
    )
    EXAMPLE_PLAYER_MATCH_STATS3 = (
        TestData_Player.EXAMPLE_PLAYER2,
        PlayerMatchStats(
            player_name='example_player_name2',
            match_id='bdae2395-0552-49bb-b543-3c3b33e758f4',
            is_custom_match=False,
            game_mode=GameMode.SQUAD,
            match_type=MatchType.NORMAL,
            DBNOs=3,
            boosts=3,
            damage_dealt=3.0,
            death_type='',
            headshot_kills=3,
            heals=3,
            win_place=3,
            kill_place=3,
            kill_streaks=3,
            kills=3,
            assists=3,
            longest_kill=3.0,
            revives=3,
            ride_distance=3.0,
            swim_distance=3.0,
            walk_distance=3.0,
            road_kills=3,
            team_kills=3,
            time_survived=3,
            vehicle_destroys=3,
            weapons_acquired=3,
        ),
    )
    EXAMPLE_PLAYER_MATCH_STATS4 = (
        TestData_Player.EXAMPLE_PLAYER2,
        PlayerMatchStats(
            player_name='example_player_name2',
            match_id='7cbaf996-cc3f-426b-bba4-ba5920da75d0',
            is_custom_match=False,
            game_mode=GameMode.SQUAD,
            match_type=MatchType.NORMAL,
            DBNOs=4,
            boosts=4,
            damage_dealt=4.0,
            death_type='',
            headshot_kills=4,
            heals=4,
            win_place=4,
            kill_place=4,
            kill_streaks=4,
            kills=4,
            assists=4,
            longest_kill=4.0,
            revives=4,
            ride_distance=4.0,
            swim_distance=4.0,
            walk_distance=4.0,
            road_kills=4,
            team_kills=4,
            time_survived=4,
            vehicle_destroys=4,
            weapons_acquired=4,
        ),
    )
    EXAMPLE_PLAYER_MATCH_STATS5 = (
        TestData_Player.EXAMPLE_PLAYER1_4,
        PlayerMatchStats(
            player_name='example_player_name1',
            match_id='f6a69afd-fb60-45da-8b40-a2e013db0f33',
            is_custom_match=False,
            game_mode=GameMode.SQUAD,
            match_type=MatchType.NORMAL,
            DBNOs=5,
            boosts=5,
            damage_dealt=5.0,
            death_type='',
            headshot_kills=5,
            heals=5,
            win_place=5,
            kill_place=5,
            kill_streaks=5,
            kills=5,
            assists=5,
            longest_kill=5.0,
            revives=5,
            ride_distance=5.0,
            swim_distance=5.0,
            walk_distance=5.0,
            road_kills=5,
            team_kills=5,
            time_survived=5,
            vehicle_destroys=5,
            weapons_acquired=5,
        ),
    )
