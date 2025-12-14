import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import json
import random

load_dotenv()
TOKEN = os.getenv('TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

CONFIG_FILE = 'config.json'

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

def save_config(data):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=4)

config = load_config()

@bot.event
async def on_ready():
    print(f'{bot.user} is now online!')
    print(f'In {len(bot.guilds)} servers')
    # Only register persistent views with custom_id buttons
    bot.add_view(TicketButtonView())
    bot.add_view(CloseTicketView())

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    await ctx.send(f"⚠️ Error: {error}")

@bot.command()
async def ping(ctx):
    await ctx.send("Pong! 🏓")

@bot.command()
@commands.has_permissions(administrator=True)
async def role(ctx, *, role_input: str = None):
    if not role_input:
        await ctx.send("❌ Usage: `!role @Support` or `!role Support`")
        return
    if role_input.startswith('<@&') and role_input.endswith('>'):
        try:
            role_id = int(role_input[3:-1])
            role = ctx.guild.get_role(role_id)
        except ValueError:
            role = None
    else:
        role = discord.utils.find(lambda r: r.name.lower() == role_input.strip().lower(), ctx.guild.roles)
    
    if not role:
        await ctx.send("❌ Role not found.")
        return
        
    config.setdefault(str(ctx.guild.id), {})['support_role'] = role.id
    save_config(config)
    await ctx.send(f"✅ Support role set to {role.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def category(ctx, *, cat_name: str = None):
    if not cat_name:
        await ctx.send("❌ Usage: `!category ticketing`")
        return
    category = discord.utils.find(lambda c: isinstance(c, discord.CategoryChannel) and c.name.lower() == cat_name.strip().lower(), ctx.guild.channels)
    if not category:
        all_cats = [c.name for c in ctx.guild.channels if isinstance(c, discord.CategoryChannel)]
        await ctx.send(f"❌ Not found. Available: {', '.join(all_cats) or 'None'}")
        return
    config.setdefault(str(ctx.guild.id), {})['category_id'] = category.id
    save_config(config)
    await ctx.send(f"✅ Default category set to **{category.name}**")

@bot.command()
@commands.has_permissions(administrator=True)
async def panel(ctx, channel: discord.TextChannel = None):
    if not channel:
        await ctx.send("❌ Usage: `!panel #support-channel`")
        return
    config.setdefault(str(ctx.guild.id), {})['panel_channel'] = channel.id
    save_config(config)
    await ctx.send(f"✅ Restricted to {channel.mention}")

@bot.command()
async def show(ctx):
    settings = config.get(str(ctx.guild.id), {})
    embed = discord.Embed(title="Current Settings", color=0x00ff99)
    
    r = settings.get('support_role')
    role_obj = ctx.guild.get_role(r) if r else None
    embed.add_field(name="Support Role", value=role_obj.mention if role_obj else "Not set", inline=False)
    
    c = settings.get('category_id')
    cat_obj = ctx.guild.get_channel(c) if c else None
    embed.add_field(name="Default Category", value=cat_obj.name if cat_obj else "Not set", inline=False)
    
    p = settings.get('panel_channel')
    chan_obj = ctx.guild.get_channel(p) if p else None
    embed.add_field(name="Panel Channel", value=chan_obj.mention if chan_obj else "Any", inline=False)
    
    types = settings.get('support_types', {})
    if types:
        lines = []
        for k, v in types.items():
            c_name = "Default"
            if v.get('category_id'):
                c_obj = ctx.guild.get_channel(v['category_id'])
                if c_obj: c_name = c_obj.name
            
            r_mention = "None"
            if v.get('role_id'):
                r_obj = ctx.guild.get_role(v['role_id'])
                if r_obj: r_mention = r_obj.mention
            
            lines.append(f"- **{k.capitalize()}**: Cat: `{c_name}`, Role: {r_mention}")
        types_str = '\n'.join(lines)
    else:
        types_str = "None set"
        
    embed.add_field(name="Support Types", value=types_str, inline=False)
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def settype(ctx, name: str, category: discord.CategoryChannel = None, role: discord.Role = None):
    """
    Usage:
    !settype <TypeName> [Category] [Role]
    Example:
    !settype billing #BillingCategory @Support
    """
    guild_id = str(ctx.guild.id)
    cat_obj = category
    role_obj = role
    
    msg = f"✅ Type '{name}' set → Category: {cat_obj.name if cat_obj else 'Default'}, Role: {role_obj.mention if role_obj else 'None'}"
    
    config.setdefault(guild_id, {})
    if 'support_types' not in config[guild_id]:
        config[guild_id]['support_types'] = {}
        
    config[guild_id]['support_types'][name.lower()] = {
        'category_id': cat_obj.id if cat_obj else None,
        'role_id': role_obj.id if role_obj else None
    }
    save_config(config)
    await ctx.send(msg)

@bot.command()
@commands.has_permissions(administrator=True)
async def removetype(ctx, *, type_name: str = None):
    """
    Usage: !removetype <TypeName>
    Example: !removetype billing
    """
    if not type_name:
        await ctx.send("❌ Usage: `!removetype <TypeName>`")
        return
    
    guild_id = str(ctx.guild.id)
    settings = config.get(guild_id, {})
    support_types = settings.get('support_types', {})
    
    key_to_remove = type_name.lower()
    
    if key_to_remove in support_types:
        del support_types[key_to_remove]
        config[guild_id]['support_types'] = support_types
        save_config(config)
        await ctx.send(f"✅ Support type **'{type_name}'** removed successfully.")
    else:
        existing = ', '.join(support_types.keys())
        await ctx.send(f"❌ Type not found. Existing types: {existing if existing else 'None'}")

@bot.command()
@commands.has_permissions(administrator=True)
async def panelsetup(ctx):
    guild_id = str(ctx.guild.id)
    allowed = config.get(guild_id, {}).get('panel_channel')
    if allowed and ctx.channel.id != allowed:
        await ctx.send("❌ Use in the allowed panel channel!")
        return
    embed = discord.Embed(title="📩 Support Tickets", description="Click to open a private ticket.", color=0x00ff99)
    await ctx.send(embed=embed, view=TicketButtonView())

class TicketTypeView(discord.ui.View):
    def __init__(self, types):
        super().__init__(timeout=300)
        options = [discord.SelectOption(label=t.capitalize(), value=t) for t in types]
        if not options:
            options = [discord.SelectOption(label="General", value="general")]
        self.type_select = discord.ui.Select(placeholder="Select support type", options=options)
        self.type_select.callback = self.on_type_select
        self.add_item(self.type_select)

    async def on_type_select(self, interaction: discord.Interaction):
        selected_type = self.type_select.values[0]
        modal = TicketModal(selected_type)
        await interaction.response.send_modal(modal)

class TicketModal(discord.ui.Modal, title="Create Support Ticket"):
    def __init__(self, selected_type=None):
        super().__init__()
        self.selected_type = selected_type
        self.description = discord.ui.TextInput(label="Briefly describe your issue", style=discord.TextStyle.paragraph, required=False)
        self.add_item(self.description)

    async def on_submit(self, interaction: discord.Interaction):
        description = self.description.value or "No description provided."
        await create_ticket(interaction, self.selected_type, description)

async def create_ticket(interaction, selected_type=None, description=None):
    guild = interaction.guild
    user = interaction.user

    # Load specific settings for the selected type
    preset = {}
    if selected_type:
        preset = config.get(str(guild.id), {}).get('support_types', {}).get(selected_type.lower(), {})
    
    cat_id = preset.get('category_id') or config.get(str(guild.id), {}).get('category_id')
    category = guild.get_channel(cat_id) if cat_id else None
    
    role_id = preset.get('role_id')
    temp_role = guild.get_role(role_id) if role_id else None

    suffix = f"-{random.randint(1000,9999)}"
    channel_name = f"ticket-{user.id}{suffix}"

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True,
            manage_messages=True,
            manage_channels=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            add_reactions=True
        )
    }

    support_role_id = config.get(str(guild.id), {}).get('support_role')
    if support_role_id:
        support_role = guild.get_role(support_role_id)
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

    topic_data = {'temp_role_id': temp_role.id} if temp_role else {}
    
    channel = await guild.create_text_channel(
        channel_name,
        category=category,
        overwrites=overwrites,
        topic=json.dumps(topic_data) if topic_data else None
    )

    if temp_role:
        await user.add_roles(temp_role)

    welcome = discord.Embed(
        title="Ticket Created 🎫", 
        description=f"{user.mention}, thank you for reaching out!\n**Type:** {selected_type.capitalize() if selected_type else 'General'}", 
        color=0x00ff99
    )
    await channel.send(embed=welcome)
    await channel.send(f"**Issue:** {description}\n\n\n\n", view=CloseTicketView())

    if not interaction.response.is_done():
        await interaction.response.send_message(f"Ticket created: {channel.mention}", ephemeral=True)

class TicketButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Ticket", style=discord.ButtonStyle.green, emoji="🎫", custom_id="open_ticket")
    async def open(self, interaction: discord.Interaction, button):
        guild = interaction.guild
        guild_id = str(guild.id)
        types = list(config.get(guild_id, {}).get('support_types', {}).keys())
        type_view = TicketTypeView(types)
        await interaction.response.send_message(
            "Select your support type:",
            view=type_view,
            ephemeral=True
        )

class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, emoji="🔒", custom_id="close_ticket")
    async def close(self, interaction: discord.Interaction, button):
        if not interaction.channel.name.startswith("ticket-"):
            await interaction.response.send_message("Only in ticket channels.", ephemeral=True)
            return
        view = ConfirmationView(interaction.channel, interaction.user)
        await interaction.response.send_message("⚠️ Are you sure you want to close this ticket?", view=view, ephemeral=False)

class ConfirmationView(discord.ui.View):
    def __init__(self, channel, requester):
        super().__init__(timeout=60)
        self.channel = channel
        self.requester = requester

    @discord.ui.button(label="Yes, Close", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button):
        if interaction.user != self.requester and not interaction.user.guild_permissions.administrator:
            # Note: You might want to allow support staff to close tickets too.
            # Currently only the opener (requester) or an admin can close.
            await interaction.response.send_message("Only the ticket owner or admin can close.", ephemeral=True)
            return
            
        if self.channel.topic:
            try:
                data = json.loads(self.channel.topic)
                role_id = data.get('temp_role_id')
                if role_id:
                    role = interaction.guild.get_role(role_id)
                    if role and role in self.requester.roles:
                        await self.requester.remove_roles(role)
            except:
                pass
        
        await interaction.response.edit_message(content="🔒 Ticket closing...", view=None)
        await self.channel.delete()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button):
        await interaction.response.edit_message(content="Close cancelled.", view=None)

# Removed unused MaxTicketsView and DuplicateTicketView to keep the file clean
# since you specified "unlimited tickets" in the logic.

bot.run(TOKEN)