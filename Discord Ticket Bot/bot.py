import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import json
import random
import traceback

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
    bot.add_view(TicketButtonView())
    bot.add_view(CloseTicketView())
    bot.add_view(DashboardView())
    print("✅ All persistent views registered!")

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
        
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def panelsetup(ctx):
    guild_id = str(ctx.guild.id)
    allowed = config.get(guild_id, {}).get('panel_channel')
    if allowed and ctx.channel.id != allowed:
        await ctx.send("❌ Use in the allowed panel channel!")
        return
    
    guild_config = config.get(guild_id, {})
    title = guild_config.get('panel_title', '📩 Support Tickets')
    description = guild_config.get('panel_description', 'Click to open a private ticket.')
    
    try:
        color = int(guild_config.get("embed_color", "0x00ff99").replace("#", "0x"), 16)
    except:
        color = 0x00ff99
    
    embed = discord.Embed(title=title, description=description, color=color)
    await ctx.send(embed=embed, view=TicketButtonView())

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
    cat_id = config.get(str(guild.id), {}).get('category_id')
    category = guild.get_channel(cat_id) if cat_id else None
    suffix = f"-{random.randint(1000,9999)}"
    channel_name = f"ticket-{user.id}{suffix}"

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True, manage_channels=True, embed_links=True, attach_files=True, read_message_history=True, add_reactions=True)
    }

    support_role_id = config.get(str(guild.id), {}).get('support_role')
    if support_role_id:
        support_role = guild.get_role(support_role_id)
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

    channel = await guild.create_text_channel(channel_name, category=category, overwrites=overwrites)
    guild_config = config.get(str(guild.id), {})
    welcome_msg = guild_config.get('welcome_message', 'thank you for reaching out!')
    
    try:
        color = int(guild_config.get("embed_color", "0x00ff99").replace("#", "0x"), 16)
    except:
        color = 0x00ff99

    welcome = discord.Embed(title="Ticket Created 🎫", description=f"{user.mention}, {welcome_msg}\n**Type:** General", color=color)
    await channel.send(embed=welcome)
    await channel.send(f"**Issue:** {description}\n\n\n\n", view=CloseTicketView())

    if not interaction.response.is_done():
        await interaction.response.send_message(f"Ticket created: {channel.mention}", ephemeral=True)

class TicketButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Ticket", style=discord.ButtonStyle.green, emoji="🎫", custom_id="open_ticket")
    async def open(self, interaction: discord.Interaction, button):
        modal = TicketModal("general")
        await interaction.response.send_modal(modal)

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
            await interaction.response.send_message("Only the ticket owner or admin can close.", ephemeral=True)
            return
        await interaction.response.edit_message(content="🔒 Ticket closing...", view=None)
        await self.channel.delete()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button):
        await interaction.response.edit_message(content="Close cancelled.", view=None)

DASHBOARD_CHANNEL_NAME = "ticket-bot-dashboard"
DASHBOARD_CONFIG_KEY = "dashboard_channel_id"

class BackendSettingModal(discord.ui.Modal):
    def __init__(self, setting_type, current_display):
        titles = {'support_role': 'Set Support Role', 'category': 'Set Category', 'panel_channel': 'Set Panel Channel'}
        super().__init__(title=titles.get(setting_type, 'Update Setting'))
        self.setting_type = setting_type
        
        # Labels with descriptions for clarity
        labels = {'support_role': 'Role Name', 'category': 'Category Name', 'panel_channel': 'Channel Name'}
        
        # Detailed placeholders that explain what each setting does
        placeholders = {
            'support_role': 'Role that can see and manage tickets (e.g. Support)',
            'category': 'Category where ticket channels will be created (e.g. TICKETS)',
            'panel_channel': 'Restrict !panelsetup to specific channel (e.g. support)'
        }
        
        self.input = discord.ui.TextInput(
            label=labels.get(setting_type, 'Value'),
            style=discord.TextStyle.short,
            default=current_display or "",
            placeholder=placeholders.get(setting_type, "Enter value or leave empty to clear"),
            required=False
        )
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            value = self.input.value.strip()
            guild = interaction.guild
            guild_config = config.setdefault(str(guild.id), {})
            
            if not value:
                if self.setting_type == 'support_role':
                    guild_config.pop('support_role', None)
                    msg = "Support role cleared!"
                elif self.setting_type == 'category':
                    guild_config.pop('category_id', None)
                    msg = "Category cleared!"
                elif self.setting_type == 'panel_channel':
                    guild_config.pop('panel_channel', None)
                    msg = "Panel channel restriction removed!"
                save_config(config)
                await update_dashboard_message(guild)
                await interaction.response.send_message(f"✅ {msg}", ephemeral=True)
                return
            
            if self.setting_type == 'support_role':
                if value.startswith('<@&') and value.endswith('>'):
                    try:
                        role_id = int(value[3:-1])
                        role = guild.get_role(role_id)
                    except ValueError:
                        role = None
                else:
                    role = discord.utils.find(lambda r: r.name.lower() == value.lower(), guild.roles)
                
                if role:
                    guild_config['support_role'] = role.id
                    save_config(config)
                    await update_dashboard_message(guild)
                    await interaction.response.send_message(f"✅ Support role set to {role.mention}!", ephemeral=True)
                else:
                    await interaction.response.send_message(f"❌ Role '{value}' not found!", ephemeral=True)
            
            elif self.setting_type == 'category':
                category = discord.utils.find(lambda c: isinstance(c, discord.CategoryChannel) and c.name.lower() == value.lower(), guild.channels)
                if category:
                    guild_config['category_id'] = category.id
                    save_config(config)
                    await update_dashboard_message(guild)
                    await interaction.response.send_message(f"✅ Category set to **{category.name}**!", ephemeral=True)
                else:
                    all_cats = [c.name for c in guild.channels if isinstance(c, discord.CategoryChannel)]
                    await interaction.response.send_message(f"❌ Category '{value}' not found!\n**Available:** {', '.join(all_cats) if all_cats else 'None'}", ephemeral=True)
            
            elif self.setting_type == 'panel_channel':
                if value.startswith('<#') and value.endswith('>'):
                    try:
                        channel_id = int(value[2:-1])
                        channel = guild.get_channel(channel_id)
                    except ValueError:
                        channel = None
                else:
                    channel = discord.utils.find(lambda c: isinstance(c, discord.TextChannel) and c.name.lower() == value.lower(), guild.channels)
                
                if channel and isinstance(channel, discord.TextChannel):
                    guild_config['panel_channel'] = channel.id
                    save_config(config)
                    await update_dashboard_message(guild)
                    await interaction.response.send_message(f"✅ Panel channel restricted to {channel.mention}!", ephemeral=True)
                else:
                    await interaction.response.send_message(f"❌ Text channel '{value}' not found!", ephemeral=True)
        except Exception as e:
            print(f"❌ Error in BackendSettingModal: {e}")
            traceback.print_exc()
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Error occurred!", ephemeral=True)

class FrontendSettingModal(discord.ui.Modal):
    def __init__(self, field_key, current_value, label, placeholder=None):
        super().__init__(title=f"Update {label}")
        self.field_key = field_key
        self.label = label
        
        # Detailed placeholders explaining what each frontend setting controls
        detailed_placeholders = {
            'panel_title': 'The title shown at the top of the ticket panel embed',
            'panel_description': 'The description text shown in the ticket panel embed',
            'button_label': 'The text displayed on the "Open Ticket" button',
            'button_emoji': 'The emoji shown next to the button label (e.g. 🎫)',
            'embed_color': 'Hex color code for embeds (e.g. 0x00ff99 or #00ff99)',
            'welcome_message': 'Message shown when a new ticket is created'
        }
        
        final_placeholder = placeholder or detailed_placeholders.get(self.field_key, "Leave empty to reset to default")
        
        self.input = discord.ui.TextInput(
            label=label[:45],
            style=discord.TextStyle.paragraph if "description" in label.lower() or "message" in label.lower() else discord.TextStyle.short,
            default=current_value or "",
            placeholder=final_placeholder,
            required=False
        )
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            value = self.input.value.strip() if self.input.value.strip() else None
            guild_config = config.setdefault(str(interaction.guild.id), {})
            
            if self.field_key == 'embed_color' and value:
                if not value.startswith(('#', '0x')):
                    await interaction.response.send_message("❌ Color must start with # or 0x", ephemeral=True)
                    return
                try:
                    int(value.replace("#", "0x"), 16)
                except ValueError:
                    await interaction.response.send_message("❌ Invalid hex color!", ephemeral=True)
                    return
            
            if value is None:
                guild_config.pop(self.field_key, None)
                msg = f"{self.label} reset to default!"
            else:
                guild_config[self.field_key] = value
                msg = f"{self.label} updated!"
            
            save_config(config)
            await update_dashboard_message(interaction.guild)
            await interaction.response.send_message(f"✅ {msg}", ephemeral=True)
        except Exception as e:
            print(f"❌ Error in FrontendSettingModal: {e}")
            traceback.print_exc()
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Error occurred!", ephemeral=True)

class DashboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin only!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Set Support Role", style=discord.ButtonStyle.primary, row=0, custom_id="dash_support_role")
    async def support_role(self, interaction: discord.Interaction, button):
        try:
            guild_config = config.get(str(interaction.guild.id), {})
            role_id = guild_config.get('support_role')
            role = interaction.guild.get_role(role_id) if role_id else None
            current = role.name if role else ""
            modal = BackendSettingModal('support_role', current)
            await interaction.response.send_modal(modal)
        except Exception as e:
            print(f"Error: {e}")
            traceback.print_exc()
            await interaction.response.send_message(f"❌ Error!", ephemeral=True)

    @discord.ui.button(label="Set Category", style=discord.ButtonStyle.primary, row=0, custom_id="dash_category")
    async def category(self, interaction: discord.Interaction, button):
        try:
            guild_config = config.get(str(interaction.guild.id), {})
            cat_id = guild_config.get('category_id')
            cat = interaction.guild.get_channel(cat_id) if cat_id else None
            current = cat.name if cat else ""
            modal = BackendSettingModal('category', current)
            await interaction.response.send_modal(modal)
        except Exception as e:
            print(f"Error: {e}")
            traceback.print_exc()
            await interaction.response.send_message(f"❌ Error!", ephemeral=True)

    @discord.ui.button(label="Restrict Panel Channel", style=discord.ButtonStyle.primary, row=0, custom_id="dash_panel_channel")
    async def panel_channel(self, interaction: discord.Interaction, button):
        try:
            guild_config = config.get(str(interaction.guild.id), {})
            chan_id = guild_config.get('panel_channel')
            chan = interaction.guild.get_channel(chan_id) if chan_id else None
            current = chan.name if chan else ""
            modal = BackendSettingModal('panel_channel', current)
            await interaction.response.send_modal(modal)
        except Exception as e:
            print(f"Error: {e}")
            traceback.print_exc()
            await interaction.response.send_message(f"❌ Error!", ephemeral=True)

    @discord.ui.button(label="Panel Title", style=discord.ButtonStyle.secondary, row=1, custom_id="dash_panel_title")
    async def panel_title(self, interaction: discord.Interaction, button):
        try:
            current = config.get(str(interaction.guild.id), {}).get("panel_title", "")
            modal = FrontendSettingModal("panel_title", current, "Panel Title")
            await interaction.response.send_modal(modal)
        except Exception as e:
            print(f"Error: {e}")
            traceback.print_exc()
            await interaction.response.send_message(f"❌ Error!", ephemeral=True)

    @discord.ui.button(label="Panel Description", style=discord.ButtonStyle.secondary, row=1, custom_id="dash_panel_desc")
    async def panel_desc(self, interaction: discord.Interaction, button):
        try:
            current = config.get(str(interaction.guild.id), {}).get("panel_description", "")
            modal = FrontendSettingModal("panel_description", current, "Panel Description")
            await interaction.response.send_modal(modal)
        except Exception as e:
            print(f"Error: {e}")
            traceback.print_exc()
            await interaction.response.send_message(f"❌ Error!", ephemeral=True)

    @discord.ui.button(label="Button Label", style=discord.ButtonStyle.secondary, row=1, custom_id="dash_button_label")
    async def button_label(self, interaction: discord.Interaction, button):
        try:
            current = config.get(str(interaction.guild.id), {}).get("button_label", "")
            modal = FrontendSettingModal("button_label", current, "Button Label")
            await interaction.response.send_modal(modal)
        except Exception as e:
            print(f"Error: {e}")
            traceback.print_exc()
            await interaction.response.send_message(f"❌ Error!", ephemeral=True)

    @discord.ui.button(label="Button Emoji", style=discord.ButtonStyle.secondary, row=2, custom_id="dash_button_emoji")
    async def button_emoji(self, interaction: discord.Interaction, button):
        try:
            current = config.get(str(interaction.guild.id), {}).get("button_emoji", "")
            modal = FrontendSettingModal("button_emoji", current, "Button Emoji")
            await interaction.response.send_modal(modal)
        except Exception as e:
            print(f"Error: {e}")
            traceback.print_exc()
            await interaction.response.send_message(f"❌ Error!", ephemeral=True)

    @discord.ui.button(label="Embed Color", style=discord.ButtonStyle.secondary, row=2, custom_id="dash_embed_color")
    async def embed_color(self, interaction: discord.Interaction, button):
        try:
            current = config.get(str(interaction.guild.id), {}).get("embed_color", "")
            modal = FrontendSettingModal("embed_color", current, "Embed Color")
            await interaction.response.send_modal(modal)
        except Exception as e:
            print(f"Error: {e}")
            traceback.print_exc()
            await interaction.response.send_message(f"❌ Error!", ephemeral=True)

    @discord.ui.button(label="Welcome Message", style=discord.ButtonStyle.secondary, row=2, custom_id="dash_welcome_msg")
    async def welcome_msg(self, interaction: discord.Interaction, button):
        try:
            current = config.get(str(interaction.guild.id), {}).get("welcome_message", "")
            modal = FrontendSettingModal("welcome_message", current, "Welcome Message")
            await interaction.response.send_modal(modal)
        except Exception as e:
            print(f"Error: {e}")
            traceback.print_exc()
            await interaction.response.send_message(f"❌ Error!", ephemeral=True)

    @discord.ui.button(label="Refresh Dashboard", style=discord.ButtonStyle.green, emoji="🔄", row=3, custom_id="dash_refresh")
    async def refresh(self, interaction: discord.Interaction, button):
        try:
            await update_dashboard_message(interaction.guild)
            await interaction.response.send_message("🔄 Refreshed!", ephemeral=True)
        except Exception as e:
            print(f"Error: {e}")
            traceback.print_exc()
            await interaction.response.send_message(f"❌ Error!", ephemeral=True)

async def update_dashboard_message(guild: discord.Guild):
    try:
        guild_config = config.get(str(guild.id), {})
        support_role = None
        support_role_id = guild_config.get('support_role')
        if support_role_id:
            support_role = guild.get_role(support_role_id)
        category = None
        cat_id = guild_config.get('category_id')
        if cat_id:
            category = guild.get_channel(cat_id)
        panel_channel = None
        chan_id = guild_config.get('panel_channel')
        if chan_id:
            panel_channel = guild.get_channel(chan_id)
        panel_title = guild_config.get('panel_title', '📩 Support Tickets')
        panel_desc = guild_config.get('panel_description', 'Click to open a private ticket.')
        button_label = guild_config.get('button_label', 'Open Ticket')
        button_emoji = guild_config.get('button_emoji', '🎫')
        embed_color_str = guild_config.get('embed_color', '0x00ff99')
        welcome_msg = guild_config.get('welcome_message', 'thank you for reaching out!')
        try:
            color = int(embed_color_str.replace("#", "0x"), 16)
        except:
            color = 0x00ff99
        embed = discord.Embed(title="🎛️ Ticket Bot Dashboard", color=color)
        backend_value = f"**Support Role:**\n{support_role.mention if support_role else '`Not set`'}\n\n**Category:**\n{f'`{category.name}`' if category else '`Not set`'}\n\n**Panel Channel:**\n{panel_channel.mention if panel_channel else '`Any channel`'}"
        embed.add_field(name="🔧 Backend Settings", value=backend_value, inline=False)
        frontend_value = f"**Panel Title:**\n`{panel_title}`\n\n**Panel Description:**\n`{panel_desc}`\n\n**Button:**\n{button_emoji} `{button_label}`\n\n**Embed Color:**\n`{embed_color_str}`\n\n**Welcome Message:**\n`{welcome_msg}`"
        embed.add_field(name="🎨 Frontend Settings", value=frontend_value, inline=False)
        embed.set_footer(text="Use buttons below to configure • Changes apply instantly")
        dashboard_channel_id = guild_config.get(DASHBOARD_CONFIG_KEY)
        dashboard_channel = guild.get_channel(dashboard_channel_id) if dashboard_channel_id else None
        if dashboard_channel:
            message = None
            async for msg in dashboard_channel.history(limit=10):
                if msg.author == guild.me and msg.embeds and len(msg.embeds) > 0 and msg.embeds[0].title == "🎛️ Ticket Bot Dashboard":
                    message = msg
                    break
            if message:
                await message.edit(embed=embed, view=DashboardView())
            else:
                await dashboard_channel.send(embed=embed, view=DashboardView())
    except Exception as e:
        print(f"Error updating dashboard: {e}")
        traceback.print_exc()

@bot.command()
@commands.has_permissions(administrator=True)
async def setupdashboard(ctx):
    try:
        guild = ctx.guild
        guild_config = config.setdefault(str(guild.id), {})
        dashboard_channel = discord.utils.get(guild.text_channels, name=DASHBOARD_CHANNEL_NAME)
        if not dashboard_channel:
            overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False), guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True), ctx.author: discord.PermissionOverwrite(view_channel=True, send_messages=True)}
            for member in guild.members:
                if member.guild_permissions.administrator:
                    overwrites[member] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
            dashboard_channel = await guild.create_text_channel(name=DASHBOARD_CHANNEL_NAME, overwrites=overwrites, topic="Admin dashboard for ticket bot")
        guild_config[DASHBOARD_CONFIG_KEY] = dashboard_channel.id
        save_config(config)
        await dashboard_channel.purge(limit=50)
        await update_dashboard_message(guild)
        await ctx.send(f"✅ Dashboard created in {dashboard_channel.mention}")
    except Exception as e:
        print(f"Error in setupdashboard: {e}")
        traceback.print_exc()
        await ctx.send(f"❌ Error setting up dashboard!")

bot.run(TOKEN)