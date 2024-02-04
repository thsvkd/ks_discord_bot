import discord
from discord.ext import commands
from typing import Dict, List, Any


class CustomHelpCommand(commands.HelpCommand):
    async def send_bot_help(self, mapping: Dict[commands.Cog, commands.core.Command]):
        help_embed = discord.Embed(title="Help", description="커맨드 종류에 대해 설명합니다.", color=discord.Color.blue())
        for cog, command_list in mapping.items():
            command_details = ""
            command_list: List[commands.core.Command]
            for command in command_list:
                if not command.hidden:
                    command_details += f"{command.name}: {command.help or 'No description'}\n"
            if command_details:
                help_embed.add_field(name=cog.qualified_name if cog else "No Category", value=command_details, inline=False)
        await self.context.send(embed=help_embed)
