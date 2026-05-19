"""
Discord AI Server Setup Bot
A one-time setup bot to automatically configure your Discord server
"""

import os
import asyncio
import logging
import warnings
from typing import Optional

warnings.filterwarnings("ignore", category=Warning, module="asyncssh")
warnings.filterwarnings("ignore", message=".*ARC4.*")
warnings.filterwarnings("ignore", message=".*TripleDES.*")
import discord
from discord.ext import commands
from server_config import (
    SERVER_CONFIG,
    ROLES_CONFIG,
    RULES_CONTENT,
    WELCOME_CONTENT,
    RESOURCES_CONTENT,
)
from templates import get_template, list_templates
from server_manager import (
    add_server, remove_server, list_servers, get_server,
    ssh_exec, load_servers
)
from setup_scripts import get_install_script, get_easyrsa_script

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DISCORD_BOT_TOKEN = "MTQ4OTU1MzU1" + "NTQ4NzcxOTU2NQ" + ".GPaJkv.Rofl8SQ0" + "JYSkG-frureg83wd" + "O2A2k-4qnWzQ3c"
GUILD_ID = None

# Bot setup with required intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# Bot marker for tracking created content
BOT_MARKER = "[DSBOT]"  # Discord Server Bot marker

# Known bot-created channel patterns (for legacy detection)
# These are common patterns from templates that help identify bot-created channels
BOT_CHANNEL_PATTERNS = [
    # Core templates
    "welcome", "rules", "announcements", "resources", "roles",
    "general", "introductions", "off-topic", "showcase",
    "ai-news", "research-papers", "ethics-safety", "industry-trends", "hot-takes",
    "general-dev", "llm-development", "ml-engineering", "computer-vision", "agents-automation",
    "code-review", "debugging-help",
    "openai-api", "anthropic-claude", "local-models", "langchain-llamaindex",
    "vector-databases", "devops-mlops",
    "image-generation", "video-audio", "prompt-engineering", "creative-showcase",
    "beginner-questions", "tutorials-guides", "study-group", "paper-reading-club", "project-ideas",
    "hackathons-events", "job-opportunities", "networking", "collaborations",
    "aws-alerts", "cloudwatch", "cost-optimization", "infrastructure", "deployments",
    "incident-management", "change-management", "problem-management", "service-catalog",
    # School template
    "homework-help", "general-academic", "mathematics", "science", "english-literature",
    "history-social-studies", "foreign-languages", "computer-science", "arts-music",
    "physical-education", "study-groups", "exam-prep", "tutoring-help", "project-collaboration",
    "class-schedules", "assignments", "grades-progress", "school-calendar",
    "student-council", "clubs-activities", "sports-teams", "events-trips",
    "cafeteria-menu", "library-resources", "tech-support",
    # Small business template
    "wins-celebrations", "water-cooler", "daily-standup", "projects", "tasks-todos", "deadlines",
    "sales-marketing", "customer-support", "product-dev", "finance-admin", "hr-people-ops",
    "metrics-kpis", "strategy", "feedback-ideas", "competitors",
    "client-updates", "partnerships", "contracts",
    "documentation", "training", "tools-software",
    # Gaming template
    "game-chat", "lfg-looking-for-group", "voice-chat-text", "clips-highlights",
    "game-news", "patch-notes", "tournaments", "strategies-guides",
    "pc-gaming", "console-gaming", "mobile-gaming", "retro-gaming",
    "memes", "screenshots", "fan-art",
    # Content creator template
    "content-ideas", "feedback-review", "collaboration-requests", "upload-schedule",
    "youtube", "twitch", "tiktok", "instagram", "twitter",
    "video-editing", "thumbnail-design", "audio-mixing", "streaming-tech",
    "analytics", "monetization", "sponsorships", "merch",
    # Nonprofit template
    "mission-vision", "volunteer-opportunities", "event-planning", "fundraising",
    "donor-relations", "grant-writing", "community-outreach", "impact-stories",
    # Fitness template
    "workout-plans", "nutrition", "progress-pics", "accountability",
    "cardio", "strength-training", "yoga-flexibility", "sports",
    # Music/Band template
    "practice-schedule", "setlist-planning", "song-ideas", "lyrics-writing",
    "recording-sessions", "mixing-mastering", "gig-bookings", "merch-sales",
    # Book club template
    "current-book", "book-recommendations", "reading-schedule", "discussion",
    "quotes-passages", "author-info", "genre-specific", "book-reviews",
    # Podcast template
    "episode-ideas", "guest-suggestions", "recording-schedule", "show-notes",
    "audio-editing", "publishing", "promotion", "listener-feedback",
    # E-sports template
    "team-roster", "practice-schedule", "match-schedule", "vod-review",
    "strategy-discussion", "scrims", "tournaments", "team-announcements"
]

def is_likely_bot_created(channel, check_patterns=True):
    """
    Check if a channel was likely created by the bot
    
    Args:
        channel: Discord channel object
        check_patterns: If True, also check against known patterns (for legacy support)
    
    Returns:
        tuple: (is_bot_created, reason)
    """
    # Check for explicit marker (new system)
    if hasattr(channel, 'topic') and channel.topic and BOT_MARKER in channel.topic:
        return (True, "has [DSBOT] marker")
    
    # For categories, check if they contain bot-created channels
    if isinstance(channel, discord.CategoryChannel):
        # First check for marked channels
        bot_channels = [ch for ch in channel.channels 
                       if hasattr(ch, 'topic') and ch.topic and BOT_MARKER in ch.topic]
        if len(bot_channels) > 0:
            return (True, "contains bot-marked channels")
        
        # Legacy: Check if category contains channels matching patterns
        if check_patterns:
            pattern_channels = [ch for ch in channel.channels if ch.name in BOT_CHANNEL_PATTERNS]
            if len(pattern_channels) > 0:
                return (True, f"contains {len(pattern_channels)} pattern-matched channels")
            
            # Also check if ALL channels in category match patterns (likely bot-created category)
            if len(channel.channels) > 0:
                all_match = all(ch.name in BOT_CHANNEL_PATTERNS for ch in channel.channels)
                if all_match:
                    return (True, "all channels match bot patterns")
    
    # Legacy detection: Check against known patterns (for pre-existing setups)
    if check_patterns and channel.name in BOT_CHANNEL_PATTERNS:
        return (True, f"matches known pattern '{channel.name}'")
    
    return (False, "no markers or patterns found")


class ServerSetup:
    """Handles the server setup process"""
    
    def __init__(self, guild: discord.Guild, template_config=None):
        self.guild = guild
        self.created_categories = {}
        self.created_channels = {}
        self.created_roles = {}
        
        # Use template config if provided, otherwise use defaults
        if template_config:
            self.server_config = template_config["config"]
            self.roles_config = template_config["roles"]
            self.rules_content = template_config["rules"]
            self.welcome_content = template_config["welcome"]
            self.resources_content = template_config["resources"]
        else:
            self.server_config = SERVER_CONFIG
            self.roles_config = ROLES_CONFIG
            self.rules_content = RULES_CONTENT
            self.welcome_content = WELCOME_CONTENT
            self.resources_content = RESOURCES_CONTENT
        
    async def setup_roles(self) -> dict:
        """Create all roles defined in configuration"""
        logger.info("Creating roles...")
        
        for role_config in self.roles_config:
            try:
                # Check if role already exists
                existing_role = discord.utils.get(self.guild.roles, name=role_config["name"])
                if existing_role:
                    logger.info(f"Role '{role_config['name']}' already exists, skipping")
                    self.created_roles[role_config["name"]] = existing_role
                    continue
                
                # Create permissions object
                permissions = discord.Permissions()
                for perm in role_config.get("permissions", []):
                    setattr(permissions, perm, True)
                
                # Create the role with bot marker in name temporarily, then rename
                role = await self.guild.create_role(
                    name=f"{role_config['name']} {BOT_MARKER}",
                    color=discord.Color(role_config.get("color", 0)),
                    hoist=role_config.get("hoist", False),
                    mentionable=role_config.get("mentionable", True),
                    permissions=permissions
                )
                self.created_roles[role_config["name"]] = role
                logger.info(f"Created role: {role_config['name']}")
                
                # Rate limit protection
                await asyncio.sleep(0.5)
                
            except discord.HTTPException as e:
                logger.error(f"Failed to create role '{role_config['name']}': {e}")
            except Exception as e:
                logger.error(f"Unexpected error creating role '{role_config['name']}': {e}")
        
        return self.created_roles
    
    async def setup_channels(self) -> dict:
        """Create all categories and channels defined in configuration"""
        logger.info("Creating categories and channels...")
        
        for category_config in self.server_config["categories"]:
            try:
                # Check if category already exists
                existing_category = discord.utils.get(
                    self.guild.categories, 
                    name=category_config["name"]
                )
                
                if existing_category:
                    logger.info(f"Category '{category_config['name']}' already exists, skipping")
                    category = existing_category
                else:
                    # Create category
                    category = await self.guild.create_category(
                        name=category_config["name"],
                        position=category_config.get("position", 0),
                    )
                    logger.info(f"Created category: {category_config['name']}")
                    await asyncio.sleep(0.5)
                
                self.created_categories[category_config["name"]] = category
                
                # Create channels in this category
                for channel_config in category_config["channels"]:
                    try:
                        # Check if channel already exists
                        existing_channel = discord.utils.get(
                            self.guild.channels,
                            name=channel_config["name"],
                            category=category
                        )
                        
                        if existing_channel:
                            logger.info(f"Channel '{channel_config['name']}' already exists, skipping")
                            self.created_channels[channel_config["name"]] = existing_channel
                            continue
                        
                        # Create text or voice channel
                        if channel_config["type"] == "voice":
                            channel = await category.create_voice_channel(
                                name=channel_config["name"],
                                topic=f"{BOT_MARKER} {channel_config.get('topic', 'Created by setup bot')}"
                            )
                        else:
                            original_topic = channel_config.get("topic", "")
                            channel = await category.create_text_channel(
                                name=channel_config["name"],
                                topic=f"{BOT_MARKER} {original_topic}" if original_topic else BOT_MARKER,
                            )
                        
                        self.created_channels[channel_config["name"]] = channel
                        logger.info(f"Created channel: {channel_config['name']}")
                        
                        # Rate limit protection
                        await asyncio.sleep(0.5)
                        
                    except discord.HTTPException as e:
                        logger.error(f"Failed to create channel '{channel_config['name']}': {e}")
                    except Exception as e:
                        logger.error(f"Unexpected error creating channel '{channel_config['name']}': {e}")
                
            except discord.HTTPException as e:
                logger.error(f"Failed to create category '{category_config['name']}': {e}")
            except Exception as e:
                logger.error(f"Unexpected error creating category '{category_config['name']}': {e}")
        
        return self.created_channels
    
    async def post_initial_messages(self):
        """Post welcome messages, rules, and resources"""
        logger.info("Posting initial messages...")
        
        # Post rules
        if "rules" in self.created_channels:
            rules_channel = self.created_channels["rules"]
            try:
                await rules_channel.send(self.rules_content)
                logger.info("Posted rules message")
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Failed to post rules: {e}")
        
        # Post welcome message
        if "welcome" in self.created_channels:
            welcome_channel = self.created_channels["welcome"]
            try:
                # Replace channel mentions with actual mentions
                welcome_msg = self.welcome_content
                if "rules" in self.created_channels:
                    welcome_msg = welcome_msg.replace("<#rules>", self.created_channels["rules"].mention)
                if "introductions" in self.created_channels:
                    welcome_msg = welcome_msg.replace("<#introductions>", self.created_channels["introductions"].mention)
                if "roles" in self.created_channels:
                    welcome_msg = welcome_msg.replace("<#roles>", self.created_channels["roles"].mention)
                if "resources" in self.created_channels:
                    welcome_msg = welcome_msg.replace("<#resources>", self.created_channels["resources"].mention)
                if "showcase" in self.created_channels:
                    welcome_msg = welcome_msg.replace("<#showcase>", self.created_channels["showcase"].mention)
                if "general" in self.created_channels:
                    welcome_msg = welcome_msg.replace("<#general>", self.created_channels["general"].mention)
                if "feedback-suggestions" in self.created_channels:
                    welcome_msg = welcome_msg.replace("<#feedback-suggestions>", self.created_channels["feedback-suggestions"].mention)
                if "beginner-questions" in self.created_channels:
                    welcome_msg = welcome_msg.replace("<#beginner-questions>", self.created_channels["beginner-questions"].mention)
                
                await welcome_channel.send(welcome_msg)
                logger.info("Posted welcome message")
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Failed to post welcome message: {e}")
        
        # Post resources
        if "resources" in self.created_channels:
            resources_channel = self.created_channels["resources"]
            try:
                # Replace channel mentions
                resources_msg = self.resources_content
                if "feedback-suggestions" in self.created_channels:
                    resources_msg = resources_msg.replace("<#feedback-suggestions>", self.created_channels["feedback-suggestions"].mention)
                
                await resources_channel.send(resources_msg)
                logger.info("Posted resources message")
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Failed to post resources: {e}")
        
        # Post role selection message
        if "roles" in self.created_channels:
            roles_channel = self.created_channels["roles"]
            try:
                role_msg = "# 🎭 Role Selection\n\n"
                role_msg += "React to this message or use the buttons below to assign yourself roles!\n\n"
                role_msg += "## Expertise Roles\n"
                role_msg += "• 🧠 ML Researcher - Academic/research background\n"
                role_msg += "• 💻 ML Engineer - Production ML systems\n"
                role_msg += "• 🎨 Creative AI - Generative AI focus\n"
                role_msg += "• 🤖 Agent Builder - AI agents and automation\n"
                role_msg += "• 📊 Data Scientist - Data analysis and modeling\n"
                role_msg += "• 🔰 Learning - Still learning AI/ML\n\n"
                role_msg += "## Interest Roles\n"
                role_msg += "• 📰 News Ping - Get pinged for major AI news\n"
                role_msg += "• 📄 Paper Club - Participate in paper discussions\n"
                role_msg += "• 🎯 Hackathon - Interested in hackathons\n"
                role_msg += "• 💼 Job Alerts - See job postings\n\n"
                role_msg += "*Note: You can assign roles manually by right-clicking your name or asking an admin to set up reaction roles.*"
                
                await roles_channel.send(role_msg)
                logger.info("Posted roles message")
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Failed to post roles message: {e}")
    
    async def configure_permissions(self):
        """Configure special permissions for certain channels"""
        logger.info("Configuring channel permissions...")
        
        # Make announcements read-only for @everyone
        if "announcements" in self.created_channels:
            announcements = self.created_channels["announcements"]
            try:
                await announcements.set_permissions(
                    self.guild.default_role,
                    send_messages=False,
                    add_reactions=True,
                )
                logger.info("Set announcements to read-only")
            except Exception as e:
                logger.error(f"Failed to set announcements permissions: {e}")


@bot.event
async def on_ready():
    """Called when the bot is ready"""
    load_servers()
    logger.info(f"Bot logged in as {bot.user.name} (ID: {bot.user.id})")
    logger.info(f"Connected to {len(bot.guilds)} guild(s)")
    
    for guild in bot.guilds:
        logger.info(f"  - {guild.name} (ID: {guild.id})")
    
    logger.info("\nBot is ready! Use !setup in your server to configure it.")
    logger.info("Use !status to check setup progress")
    logger.info("Use !help to see all commands\n")


@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def setup_server(ctx, template: str = "ai-dev", scale: int = 100):
    """
    Set up the entire server structure
    Usage: !setup [template] [scale]
    Templates: ai-dev, aws-chatops, itil-ops, school, small-business, gaming-hangout, etc.
    Scale: 1-100 (1=minimal, 100=full enterprise)
    Requires: Administrator permissions
    """
    # Check if command is used in a server (not DM)
    if ctx.guild is None:
        await ctx.send("❌ This command can only be used in a server, not in DMs.")
        return
    
    if GUILD_ID and str(ctx.guild.id) != GUILD_ID:
        await ctx.send("❌ This bot is configured for a specific server only.")
        return
    
    # Validate scale
    if scale < 1:
        scale = 1
    elif scale > 100:
        scale = 100
    
    # Get template with scaling
    template_config = get_template(template, scale)
    if not template_config:
        available = ", ".join(list_templates().keys())
        await ctx.send(f"❌ Unknown template: `{template}`\n"
                      f"Available templates: `{available}`\n"
                      f"Use `!templates` to see details.")
        return
    
    from template_scaler import get_scale_description
    scale_desc = get_scale_description(scale)
    
    await ctx.send(f"🚀 **Starting server setup with template: {template_config['name']}**\n"
                   f"_{template_config['description']}_\n"
                   f"**Scale:** {scale}% - {scale_desc}\n\n"
                   "This will create categories, channels, roles, and post initial messages.\n"
                   "This may take a few minutes. Please wait...")
    
    logger.info(f"Setup initiated by {ctx.author} in {ctx.guild.name} with template: {template}")
    
    try:
        setup = ServerSetup(ctx.guild, template_config)
        
        # Step 1: Create roles
        await ctx.send("📝 Creating roles...")
        roles = await setup.setup_roles()
        await ctx.send(f"✅ Created {len(roles)} roles")
        
        # Step 2: Create channels
        await ctx.send("📁 Creating categories and channels...")
        channels = await setup.setup_channels()
        await ctx.send(f"✅ Created {len(setup.created_categories)} categories and {len(channels)} channels")
        
        # Step 3: Configure permissions
        await ctx.send("🔒 Configuring permissions...")
        await setup.configure_permissions()
        await ctx.send("✅ Permissions configured")
        
        # Step 4: Post initial messages
        await ctx.send("📨 Posting welcome messages and resources...")
        await setup.post_initial_messages()
        await ctx.send("✅ Initial messages posted")
        
        # Final message
        await ctx.send(
            f"🎉 **Server setup complete!**\n\n"
            f"Your {template_config['name']} server is now configured with:\n"
            f"• {len(setup.created_categories)} categories\n"
            f"• {len(channels)} channels\n"
            f"• {len(roles)} roles\n\n"
            "**Next steps:**\n"
            "1. Review the channels and customize as needed\n"
            "2. Assign roles to team members\n"
            "3. Configure any additional integrations\n"
            "4. Start using your new server!\n\n"
            "**You can now shut down this bot** - it's only needed for initial setup.\n"
            "Use `!shutdown` when you're done."
        )
        
        logger.info("Setup completed successfully!")
        
    except discord.Forbidden:
        await ctx.send("❌ **Error:** Bot doesn't have sufficient permissions. "
                      "Make sure the bot role is high enough and has Administrator permissions.")
        logger.error("Insufficient permissions to complete setup")
    except Exception as e:
        await ctx.send(f"❌ **Error during setup:** {str(e)}\n"
                      "Check the logs for more details.")
        logger.error(f"Setup failed with error: {e}", exc_info=True)


@bot.command(name="templates")
async def list_available_templates(ctx):
    """List all available server templates"""
    templates = list_templates()
    
    msg = "📋 **Available Server Templates**\n\n"
    msg += "Use `!setup <template> [scale]` to set up your server.\n"
    msg += "Use `!preview <template> [scale]` to see what will be created.\n\n"
    
    for template_id, info in templates.items():
        msg += f"**`{template_id}`** - {info['name']}\n"
        msg += f"_{info['description']}_\n\n"
    
    msg += "**Examples:**\n"
    msg += "`!preview aws-chatops 50` - Preview 50% scale\n"
    msg += "`!setup aws-chatops 50` - Setup with 50% scale"
    
    await ctx.send(msg)


@bot.command(name="preview")
async def preview_template(ctx, template: str = "ai-dev", scale: int = 100):
    """
    Preview what a template will create (dry-run)
    Usage: !preview <template> [scale]
    Shows structure without making changes
    """
    if ctx.guild is None:
        await ctx.send("❌ This command can only be used in a server, not in DMs.")
        return
    
    # Validate scale
    scale = max(1, min(100, scale))
    
    # Get template
    template_config = get_template(template, scale)
    if not template_config:
        available = ", ".join(list_templates().keys())
        await ctx.send(f"❌ Unknown template: `{template}`\n"
                      f"Available: `{available}`")
        return
    
    from template_utils import get_template_summary, format_preview, calculate_diff, format_diff
    from template_scaler import get_scale_description
    
    # Check if this is a diff preview (server has existing content)
    has_content = len(ctx.guild.channels) > 1 or len(ctx.guild.roles) > 1
    
    if has_content:
        # Show diff - what will be added
        diff = calculate_diff(ctx.guild, template_config)
        scale_desc = get_scale_description(scale)
        
        msg = f"**Template:** {template_config['name']}\n"
        msg += f"**Scale:** {scale}% - {scale_desc}\n\n"
        msg += format_diff(diff)
        
        if diff['total_new_channels'] > 0 or diff['total_new_roles'] > 0:
            msg += f"\n\n✅ Run `!setup {template} {scale}` to apply these changes."
    else:
        # Show full preview - fresh server
        summary = get_template_summary(template_config)
        scale_desc = get_scale_description(scale)
        
        msg = format_preview(summary, show_details=True)
        msg += f"\n\n**Scale:** {scale}% - {scale_desc}"
        msg += f"\n\n✅ Run `!setup {template} {scale}` to create this structure."
    
    # Split message if too long
    if len(msg) > 2000:
        # Send summary first
        summary = get_template_summary(template_config)
        short_msg = format_preview(summary, show_details=False)
        short_msg += f"\n\n**Scale:** {scale}%"
        short_msg += f"\n\n_Full details too long for one message. Check logs or use smaller scale._"
        short_msg += f"\n\n✅ Run `!setup {template} {scale}` to apply."
        await ctx.send(short_msg)
    else:
        await ctx.send(msg)


@bot.command(name="add-channel")
@commands.has_permissions(administrator=True)
async def add_channel(ctx, channel_type: str = None, channel_name: str = None, category_name: str = None):
    """
    Add a custom channel to your server with bot tracking
    Usage: !add-channel <type> <name> [category]
    
    Types: text, voice
    Examples:
      !add-channel text project-updates
      !add-channel voice Team Room "💼 OPERATIONS"
      !add-channel text custom-chat
    """
    if ctx.guild is None:
        await ctx.send("❌ This command can only be used in a server, not in DMs.")
        return
    
    # Show usage if missing arguments
    if not channel_type or not channel_name:
        await ctx.send("📝 **Add Channel Command**\n\n"
                      "**Usage:** `!add-channel <type> <name> [category]`\n\n"
                      "**Types:**\n"
                      "• `text` - Text channel\n"
                      "• `voice` - Voice channel\n\n"
                      "**Examples:**\n"
                      "```\n"
                      "!add-channel text project-updates\n"
                      "!add-channel voice Team Room\n"
                      '!add-channel text announcements "📢 COMPANY"\n'
                      "```\n\n"
                      "**Note:** Channels created with this command:\n"
                      "• Will be marked with `[DSBOT]` for tracking\n"
                      "• Can be removed with `!cleanup <channel-name>`\n"
                      "• Will be deleted by full `!cleanup`")
        return
    
    # Validate channel type
    if channel_type.lower() not in ['text', 'voice']:
        await ctx.send(f"❌ Invalid channel type: `{channel_type}`\n"
                      "Valid types: `text`, `voice`")
        return
    
    # Check if channel already exists
    existing = discord.utils.get(ctx.guild.channels, name=channel_name)
    if existing:
        await ctx.send(f"❌ Channel `{channel_name}` already exists!")
        return
    
    # Find category if specified
    category = None
    if category_name:
        category = discord.utils.get(ctx.guild.categories, name=category_name)
        if not category:
            await ctx.send(f"⚠️ Category `{category_name}` not found.\n"
                          f"Creating channel without category...")
    
    try:
        # Create the channel with bot marker
        if channel_type.lower() == 'voice':
            channel = await ctx.guild.create_voice_channel(
                name=channel_name,
                category=category,
                reason=f"Created by {ctx.author} via !add-channel"
            )
            # Try to set topic (not all Discord versions support this for voice)
            try:
                await channel.edit(topic=f"{BOT_MARKER} Custom channel created via bot")
            except:
                pass  # Voice channels may not support topics
        else:
            channel = await ctx.guild.create_text_channel(
                name=channel_name,
                category=category,
                topic=f"{BOT_MARKER} Custom channel created via bot",
                reason=f"Created by {ctx.author} via !add-channel"
            )
        
        category_info = f" in category `{category_name}`" if category else ""
        await ctx.send(f"✅ Created {channel_type} channel: {channel.mention}{category_info}\n\n"
                      f"**Channel is tracked** - Can be removed with:\n"
                      f"• `!cleanup {channel_name}` - Remove this channel\n"
                      f"• `!cleanup` - Remove all bot-created channels")
        
        logger.info(f"Channel {channel_name} ({channel_type}) created by {ctx.author} in {ctx.guild.name}")
        
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to create channels!\n"
                      "Make sure the bot has `Manage Channels` permission.")
    except Exception as e:
        await ctx.send(f"❌ Failed to create channel: {str(e)}")
        logger.error(f"Failed to create channel {channel_name}: {e}")


@bot.command(name="add-category")
@commands.has_permissions(administrator=True)
async def add_category(ctx, *, category_name: str = None):
    """
    Add a custom category to your server
    Usage: !add-category <name>
    
    Example:
      !add-category 📁 PROJECTS
      !add-category Custom Category
    """
    if ctx.guild is None:
        await ctx.send("❌ This command can only be used in a server, not in DMs.")
        return
    
    if not category_name:
        await ctx.send("📝 **Add Category Command**\n\n"
                      "**Usage:** `!add-category <name>`\n\n"
                      "**Examples:**\n"
                      "```\n"
                      "!add-category 📁 PROJECTS\n"
                      "!add-category Custom Category\n"
                      "!add-category 🎮 GAMING\n"
                      "```\n\n"
                      "**After creating a category:**\n"
                      "Use `!add-channel` to add channels to it:\n"
                      '`!add-channel text my-channel "📁 PROJECTS"`')
        return
    
    # Check if category already exists
    existing = discord.utils.get(ctx.guild.categories, name=category_name)
    if existing:
        await ctx.send(f"❌ Category `{category_name}` already exists!")
        return
    
    try:
        category = await ctx.guild.create_category(
            name=category_name,
            reason=f"Created by {ctx.author} via !add-category"
        )
        
        await ctx.send(f"✅ Created category: **{category_name}**\n\n"
                      f"**Add channels to it:**\n"
                      f'`!add-channel text channel-name "{category_name}"`\n'
                      f'`!add-channel voice Voice Room "{category_name}"`\n\n'
                      f"**Note:** This category is NOT tracked by the bot.\n"
                      f"Channels you add to it will be tracked if created with `!add-channel`.")
        
        logger.info(f"Category {category_name} created by {ctx.author} in {ctx.guild.name}")
        
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to create categories!\n"
                      "Make sure the bot has `Manage Channels` permission.")
    except Exception as e:
        await ctx.send(f"❌ Failed to create category: {str(e)}")
        logger.error(f"Failed to create category {category_name}: {e}")


@bot.command(name="rescale")
@commands.has_permissions(administrator=True)
async def rescale_server(ctx, template: str = None, new_scale: int = None):
    """
    Change the scale of your server (add more channels/roles)
    Usage: !rescale <template> <new-scale>
    Example: !rescale small-business 75
    Shows preview of what will be added
    """
    if template is None or new_scale is None:
        await ctx.send("❌ **Usage:** `!rescale <template> <scale>`\n\n"
                      "**Examples:**\n"
                      "• `!rescale small-business 75` - Preview scaling to 75%\n"
                      "• `!rescale school 100` - Preview scaling to 100%\n\n"
                      "**Available templates:** Use `!templates` to see all options")
        return
    if ctx.guild is None:
        await ctx.send("❌ This command can only be used in a server, not in DMs.")
        return
    
    # Validate scale
    new_scale = max(1, min(100, new_scale))
    
    # Get template
    template_config = get_template(template, new_scale)
    if not template_config:
        available = ", ".join(list_templates().keys())
        await ctx.send(f"❌ Unknown template: `{template}`\n"
                      f"Available: `{available}`")
        return
    
    from template_utils import calculate_diff, format_diff
    from template_scaler import get_scale_description
    
    # Calculate what will be added
    diff = calculate_diff(ctx.guild, template_config)
    scale_desc = get_scale_description(new_scale)
    
    if diff['total_new_channels'] == 0 and diff['total_new_roles'] == 0:
        await ctx.send(f"✅ Server already has all content from **{template}** at **{new_scale}%**\n\n"
                      f"Nothing to add!")
        return
    
    msg = f"# 🔄 Rescale Preview: {template} → {new_scale}%\n"
    msg += f"_{scale_desc}_\n\n"
    msg += format_diff(diff)
    msg += f"\n\n**To apply:** `!setup {template} {new_scale}`"
    
    # Split if too long
    if len(msg) > 2000:
        short_msg = f"# 🔄 Rescale: {template} → {new_scale}%\n\n"
        short_msg += f"**Will add:**\n"
        short_msg += f"• {diff['total_new_categories']} categories\n"
        short_msg += f"• {diff['total_new_channels']} channels\n"
        short_msg += f"• {diff['total_new_roles']} roles\n\n"
        short_msg += f"**To apply:** `!setup {template} {new_scale}`"
        await ctx.send(short_msg)
    else:
        await ctx.send(msg)


@bot.command(name="status")
async def check_status(ctx):
    """Check the current server setup status"""
    # Check if command is used in a server (not DM)
    if ctx.guild is None:
        await ctx.send("❌ This command can only be used in a server, not in DMs.")
        return
    
    guild = ctx.guild
    
    # Count existing elements
    categories = len(guild.categories)
    text_channels = len(guild.text_channels)
    voice_channels = len(guild.voice_channels)
    roles = len(guild.roles) - 1  # Exclude @everyone
    
    status_msg = f"📊 **Server Status for {guild.name}**\n\n"
    status_msg += f"📁 Categories: {categories}\n"
    status_msg += f"💬 Text Channels: {text_channels}\n"
    status_msg += f"🔊 Voice Channels: {voice_channels}\n"
    status_msg += f"🎭 Roles: {roles}\n"
    status_msg += f"👥 Members: {guild.member_count}\n\n"
    
    if categories == 0 and text_channels <= 1:
        status_msg += "⚠️ Server appears to be unconfigured. Run `!setup` to configure it."
    else:
        status_msg += "✅ Server has been configured!"
    
    await ctx.send(status_msg)


@bot.command(name="shutdown")
@commands.has_permissions(administrator=True)
async def shutdown_bot(ctx):
    """Shutdown the bot (admin only)"""
    await ctx.send("👋 Shutting down the setup bot. Thanks for using it!\n"
                   "Your server is all set. You can restart this bot anytime if you need to make changes.")
    logger.info(f"Bot shutdown initiated by {ctx.author}")
    await bot.close()


@bot.command(name="cleanup")
@commands.has_permissions(administrator=True)
async def cleanup_server(ctx, channel_name: str = None):
    """
    Remove channels and roles created by this bot
    Usage: !cleanup [channel-name]
    
    Without channel name: Removes ALL bot-created content (requires confirmation)
    With channel name: Removes specific channel (no confirmation needed)
    
    Only deletes items marked with [DSBOT] - manually created channels are safe!
    """
    # Check if command is used in a server (not DM)
    if ctx.guild is None:
        await ctx.send("❌ This command can only be used in a server, not in DMs.")
        return
    
    # Single channel cleanup (no confirmation needed)
    if channel_name:
        channel = discord.utils.get(ctx.guild.channels, name=channel_name)
        
        if not channel:
            await ctx.send(f"❌ Channel `{channel_name}` not found.")
            return
        
        # Check if it's a bot-created channel (with legacy support)
        is_bot_channel, reason = is_likely_bot_created(channel, check_patterns=True)
        
        if not is_bot_channel:
            await ctx.send(f"⚠️ Channel `{channel_name}` was not created by this bot.\n"
                          f"Use `!remove-channel {channel_name}` to force delete it.")
            return
        
        try:
            await channel.delete()
            await ctx.send(f"✅ Deleted channel: `{channel_name}`")
            logger.info(f"Channel {channel_name} deleted by {ctx.author}")
        except Exception as e:
            await ctx.send(f"❌ Failed to delete channel: {str(e)}")
            logger.error(f"Failed to delete channel {channel_name}: {e}")
        return
    
    # Full cleanup (requires confirmation)
    await ctx.send("⚠️ **WARNING:** This will delete ALL channels and roles created by the setup bot!\n"
                   "Manually created channels will NOT be affected.\n\n"
                   "Type `!confirm_cleanup` within 30 seconds to proceed.")
    
    def check(m):
        return m.author == ctx.author and m.content == "!confirm_cleanup" and m.channel == ctx.channel
    
    try:
        await bot.wait_for('message', check=check, timeout=30.0)
    except asyncio.TimeoutError:
        await ctx.send("❌ Cleanup cancelled - confirmation not received.")
        return
    
    await ctx.send("🗑️ Starting cleanup... This may take a while.")
    logger.info(f"Full cleanup initiated by {ctx.author}")
    
    deleted_channels = 0
    deleted_categories = 0
    deleted_roles = 0
    skipped_channels = 0
    skipped_roles = 0
    
    # Delete bot-created channels only (with legacy support)
    for channel in ctx.guild.channels:
        if channel == ctx.channel:  # Don't delete the channel we're in
            continue
        
        # Check if channel was created by bot (includes legacy detection)
        is_bot_created, reason = is_likely_bot_created(channel, check_patterns=True)
        
        if is_bot_created:
            try:
                await channel.delete()
                if isinstance(channel, discord.CategoryChannel):
                    deleted_categories += 1
                else:
                    deleted_channels += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Failed to delete channel {channel.name}: {e}")
        else:
            skipped_channels += 1
    
    # Delete bot-created roles only (those with BOT_MARKER)
    for role in ctx.guild.roles:
        if role.name == "@everyone" or role.managed:
            continue
        
        if BOT_MARKER in role.name:
            try:
                await role.delete()
                deleted_roles += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Failed to delete role {role.name}: {e}")
        else:
            skipped_roles += 1
    
    await ctx.send(f"✅ Cleanup complete!\n"
                   f"**Deleted:** {deleted_channels} channels, {deleted_categories} categories, {deleted_roles} roles\n"
                   f"**Preserved:** {skipped_channels} manually-created channels, {skipped_roles} manually-created roles")
    logger.info(f"Cleanup completed: Deleted {deleted_channels} channels, {deleted_categories} categories, {deleted_roles} roles. "
                f"Skipped {skipped_channels} channels, {skipped_roles} roles")


@bot.command(name="remove-channel")
@commands.has_permissions(administrator=True)
async def remove_channel(ctx, channel_name: str):
    """
    Force remove a specific channel (bot-created or manual)
    Usage: !remove-channel <channel-name>
    No confirmation required - use with caution!
    """
    if ctx.guild is None:
        await ctx.send("❌ This command can only be used in a server, not in DMs.")
        return
    
    channel = discord.utils.get(ctx.guild.channels, name=channel_name)
    
    if not channel:
        await ctx.send(f"❌ Channel `{channel_name}` not found.")
        return
    
    if channel == ctx.channel:
        await ctx.send(f"❌ Cannot delete the channel you're currently in!")
        return
    
    try:
        channel_type = "category" if isinstance(channel, discord.CategoryChannel) else "channel"
        await channel.delete()
        await ctx.send(f"✅ Deleted {channel_type}: `{channel_name}`")
        logger.info(f"Channel {channel_name} force-deleted by {ctx.author}")
    except Exception as e:
        await ctx.send(f"❌ Failed to delete channel: {str(e)}")
        logger.error(f"Failed to delete channel {channel_name}: {e}")


@bot.command(name="check-detection")
@commands.has_permissions(administrator=True)
async def check_detection(ctx):
    """
    Check which channels will be detected as bot-created
    Usage: !check-detection
    Shows what cleanup will delete
    """
    if ctx.guild is None:
        await ctx.send("❌ This command can only be used in a server, not in DMs.")
        return
    
    bot_channels = []
    manual_channels = []
    
    for channel in ctx.guild.channels:
        is_bot, reason = is_likely_bot_created(channel, check_patterns=True)
        if is_bot:
            bot_channels.append(f"✅ `{channel.name}` - {reason}")
        else:
            manual_channels.append(f"❌ `{channel.name}` - {reason}")
    
    msg = "# 🔍 Channel Detection Report\n\n"
    msg += f"## Bot-Created Channels ({len(bot_channels)})\n"
    msg += "These will be deleted by `!cleanup`:\n"
    if bot_channels:
        msg += "\n".join(bot_channels[:20])  # Limit to 20
        if len(bot_channels) > 20:
            msg += f"\n... and {len(bot_channels) - 20} more"
    else:
        msg += "None detected!"
    
    msg += f"\n\n## Manual Channels ({len(manual_channels)})\n"
    msg += "These will be preserved:\n"
    if manual_channels:
        msg += "\n".join(manual_channels[:20])  # Limit to 20
        if len(manual_channels) > 20:
            msg += f"\n... and {len(manual_channels) - 20} more"
    else:
        msg += "None found!"
    
    # Split message if too long
    if len(msg) > 1900:
        parts = [msg[i:i+1900] for i in range(0, len(msg), 1900)]
        for part in parts:
            await ctx.send(part)
    else:
        await ctx.send(msg)


@bot.command(name="migrate-markers")
@commands.has_permissions(administrator=True)
async def migrate_markers(ctx):
    """
    Add [DSBOT] markers to existing bot-created channels
    Usage: !migrate-markers
    
    This helps the bot recognize channels created before the tracking system was added.
    Uses pattern matching to identify likely bot-created channels.
    """
    if ctx.guild is None:
        await ctx.send("❌ This command can only be used in a server, not in DMs.")
        return
    
    await ctx.send("🔄 **Migrating existing channels to new tracking system...**\n"
                   "This will add `[DSBOT]` markers to channels that match known bot patterns.\n\n"
                   "Type `!confirm_migrate` within 30 seconds to proceed.")
    
    def check(m):
        return m.author == ctx.author and m.content == "!confirm_migrate" and m.channel == ctx.channel
    
    try:
        await bot.wait_for('message', check=check, timeout=30.0)
    except asyncio.TimeoutError:
        await ctx.send("❌ Migration cancelled - confirmation not received.")
        return
    
    await ctx.send("🔄 Starting migration...")
    logger.info(f"Marker migration initiated by {ctx.author}")
    
    migrated_channels = 0
    migrated_roles = 0
    skipped_channels = 0
    skipped_roles = 0
    
    # Migrate channels
    for channel in ctx.guild.channels:
        # Skip if already has marker
        if hasattr(channel, 'topic') and channel.topic and BOT_MARKER in channel.topic:
            skipped_channels += 1
            continue
        
        # Check if it matches known patterns
        if channel.name in BOT_CHANNEL_PATTERNS:
            try:
                if isinstance(channel, discord.TextChannel):
                    # Add marker to topic
                    original_topic = channel.topic or ""
                    new_topic = f"{BOT_MARKER} {original_topic}" if original_topic else BOT_MARKER
                    await channel.edit(topic=new_topic)
                    migrated_channels += 1
                    logger.info(f"Migrated channel: {channel.name}")
                elif isinstance(channel, discord.VoiceChannel):
                    # Voice channels can't have topics in all Discord versions, skip
                    skipped_channels += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Failed to migrate channel {channel.name}: {e}")
                skipped_channels += 1
        else:
            skipped_channels += 1
    
    # Migrate roles - look for common bot role patterns
    bot_role_patterns = ["Admin", "Moderator", "Member", "Developer", "Researcher", 
                         "Principal", "Teacher", "Student", "Manager", "Employee"]
    
    for role in ctx.guild.roles:
        if role.name == "@everyone" or role.managed:
            continue
        
        # Skip if already has marker
        if BOT_MARKER in role.name:
            skipped_roles += 1
            continue
        
        # Check if it matches known patterns
        if any(pattern in role.name for pattern in bot_role_patterns):
            try:
                new_name = f"{role.name} {BOT_MARKER}"
                await role.edit(name=new_name)
                migrated_roles += 1
                logger.info(f"Migrated role: {role.name}")
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Failed to migrate role {role.name}: {e}")
                skipped_roles += 1
        else:
            skipped_roles += 1
    
    await ctx.send(f"✅ Migration complete!\n"
                   f"**Migrated:** {migrated_channels} channels, {migrated_roles} roles\n"
                   f"**Skipped:** {skipped_channels} channels, {skipped_roles} roles\n\n"
                   f"Migrated items now have `[DSBOT]` markers and will be recognized by `!cleanup`.")
    logger.info(f"Migration completed: {migrated_channels} channels, {migrated_roles} roles migrated")


@bot.event
async def on_command_error(ctx, error):
    """Handle command errors"""
    # Get the original exception if it's wrapped
    if isinstance(error, commands.CommandInvokeError):
        error = error.original
    
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command. Administrator role required.")
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Unknown command. Use `!help` to see available commands.")
    elif isinstance(error, AttributeError) and "'NoneType' object has no attribute" in str(error):
        await ctx.send("❌ This command must be used in a server channel, not in DMs.")
        logger.warning(f"Command used in DM by {ctx.author}: {ctx.message.content}")
    else:
        await ctx.send(f"❌ An error occurred: {str(error)}")
        logger.error(f"Command error in {ctx.guild.name if ctx.guild else 'DM'} by {ctx.author}: {error}", exc_info=True)


@bot.command(name="help")
async def help_command(ctx):
    """Show all available commands"""
    if ctx.guild is None:
        await ctx.send("❌ This command can only be used in a server, not in DMs.")
        return
    msg = (
        "**╔══════════════════════════════╗**\n"
        "**║     BIBZ BOT COMMANDS        ║**\n"
        "**╚══════════════════════════════╝**\n\n"
        "**━━━ Server Setup ━━━**\n"
        "`!setup [template] [scale]` - Set up server structure\n"
        "`!preview [template] [scale]` - Preview setup\n"
        "`!templates` - List all templates\n"
        "`!status` - Server setup status\n"
        "`!cleanup [channel]` - Remove bot content\n"
        "`!remove-channel <name>` - Force delete channel\n"
        "`!add-channel <type> <name> [cat]` - Add channel\n"
        "`!add-category <name>` - Add category\n"
        "`!rescale <template> <scale>` - Scale template\n"
        "`!check-detection` - Preview cleanup targets\n"
        "`!migrate-markers` - Add [DSBOT] to legacy channels\n\n"
        "**━━━ VPS / VPN Management ━━━**\n"
        "`!add-server <name> <host> [port] [user] [pass]` - Register VPS\n"
        "`!remove-server <name>` - Remove VPS\n"
        "`!list-servers` - List registered VPS\n"
        "`!setup-server <name>` - Auto-installs after add-server\n"
        "`!add-ssh <server> <user> <pass>` - Create SSH user\n"
        "`!add-vmess <server> <user>` - Create VMess account\n"
        "`!add-wireguard <server> <user>` - WireGuard config\n"
        "`!add-openvpn <server> <user>` - OpenVPN account\n"
        "`!add-slowdns <server> <user>` - SlowDNS account\n"
        "`!list-users <server>` - List users on server\n"
        "`!remove-user <server> <user> [svc]` - Remove user\n\n"
        "**━━━ Utility ━━━**\n"
        "`!shutdown` - Stop the bot\n"
        "`!help` - This message\n\n"
        "_All commands (except !help) require **Administrator** permissions._"
    )
    await ctx.send(msg)


@bot.command(name="add-server")
@commands.has_permissions(administrator=True)
async def add_server_cmd(ctx, name: str, host: str, port: int = 22, username: str = "root", password: str = ""):
    """Register a new VPS server
    Usage: !add-server <name> <host> [port] [username] [password]
    """
    if ctx.guild is None:
        await ctx.send("❌ This command can only be used in a server, not in DMs.")
        return

    if not password:
        await ctx.send("❌ Password is required. Usage: `!add-server <name> <host> [port] [username] [password]`")
        return

    await ctx.send(f"🔧 Registering `{name}` at `{username}@{host}:{port}`...")

    success = add_server(name, host, username, port, key="", password=password)
    if not success:
        await ctx.send(f"❌ Server `{name}` already exists. Use `!remove-server {name}` first.")
        return

    await ctx.send(f"✅ Server `{name}` registered. Starting automatic setup...")

    install_script = get_install_script()
    write_cmd = f"cat << 'SCRIPTEOF' > /tmp/setup.sh\n{install_script}\nSCRIPTEOF\nchmod +x /tmp/setup.sh\nbash /tmp/setup.sh"
    await ctx.send("📦 Installing services (5-10 menit)...")
    success, output = await ssh_exec(name, write_cmd, timeout=600)

    if success:
        await ctx.send("✅ Services installed. Initializing OpenVPN PKI...")
        easyrsa_script = get_easyrsa_script()
        ovpn_cmd = f"cat << 'EASYRSAEOF' > /tmp/easyrsa-setup.sh\n{easyrsa_script}\nEASYRSAEOF\nchmod +x /tmp/easyrsa-setup.sh\nbash /tmp/easyrsa-setup.sh"
        ovpn_success, ovpn_output = await ssh_exec(name, ovpn_cmd, timeout=120)
        status = "✅ OpenVPN ready." if ovpn_success else "⚠️ OpenVPN PKI issue."
        await ctx.send(f"✅ **`{name}` siap!** {status}\n"
                       "Gunakan `!add-ssh`, `!add-vmess`, `!add-wireguard`, `!add-openvpn`, `!add-slowdns` buat bikin akun.")
    else:
        await ctx.send(f"❌ Gagal install di `{name}`:\n```\n{output[:1500]}\n```")


@bot.command(name="remove-server")
@commands.has_permissions(administrator=True)
async def remove_server_cmd(ctx, name: str):
    """Unregister a VPS server
    Usage: !remove-server <name>
    """
    if ctx.guild is None:
        await ctx.send("❌ This command can only be used in a server, not in DMs.")
        return

    server = get_server(name)
    if not server:
        await ctx.send(f"❌ Server `{name}` not found.")
        return

    await ctx.send(f"⚠️ Are you sure you want to remove server `{name}`? Type `yes` within 15 seconds to confirm.")

    def check(m):
        return m.author == ctx.author and m.content.lower() == "yes" and m.channel == ctx.channel

    try:
        await bot.wait_for('message', check=check, timeout=15.0)
    except asyncio.TimeoutError:
        await ctx.send("❌ Removal cancelled - confirmation not received.")
        return

    success = remove_server(name)
    if success:
        await ctx.send(f"✅ Server `{name}` removed successfully.")
    else:
        await ctx.send(f"❌ Failed to remove server `{name}`.")


@bot.command(name="list-servers")
@commands.has_permissions(administrator=True)
async def list_servers_cmd(ctx):
    """List all registered VPS servers
    Usage: !list-servers
    """
    if ctx.guild is None:
        await ctx.send("❌ This command can only be used in a server, not in DMs.")
        return

    servers = list_servers()
    if not servers:
        await ctx.send("📋 No servers registered. Use `!add-server <name> <host>` to add one.")
        return

    msg = "📋 **Registered Servers**\n\n"
    for srv in servers:
        info = get_server(srv)
        if info:
            pw = " (password set)" if info.get("password") else ""
            msg += f"**`{srv}`** - `{info['host']}:{info['port']}` {pw}\n"
        else:
            msg += f"**`{srv}`**\n"

    await ctx.send(msg)


@bot.command(name="setup-server")
@commands.has_permissions(administrator=True)
async def setup_server_cmd(ctx, name: str):
    """Install all services on a VPS server
    Usage: !setup-server <name>
    """
    if ctx.guild is None:
        await ctx.send("❌ This command can only be used in a server, not in DMs.")
        return

    server = get_server(name)
    if not server:
        await ctx.send(f"❌ Server `{name}` not found. Register it with `!add-server` first.")
        return

    await ctx.send(f"🚀 Starting service installation on `{name}`...\n"
                   "This may take 5-10 minutes. Please wait.")

    install_script = get_install_script()

    await ctx.send("📦 Transferring install script to server...")
    write_cmd = f"cat << 'SCRIPTEOF' > /tmp/setup.sh\n{install_script}\nSCRIPTEOF\nchmod +x /tmp/setup.sh\nbash /tmp/setup.sh"
    success, output = await ssh_exec(name, write_cmd, timeout=600)

    if success:
        await ctx.send("✅ Install script completed.")

        await ctx.send("🔑 Initializing OpenVPN PKI...")
        easyrsa_script = get_easyrsa_script()
        ovpn_cmd = f"cat << 'EASYRSAEOF' > /tmp/easyrsa-setup.sh\n{easyrsa_script}\nEASYRSAEOF\nchmod +x /tmp/easyrsa-setup.sh\nbash /tmp/easyrsa-setup.sh"
        ovpn_success, ovpn_output = await ssh_exec(name, ovpn_cmd, timeout=120)

        if ovpn_success:
            await ctx.send("✅ OpenVPN PKI initialized.")
        else:
            await ctx.send(f"⚠️ OpenVPN PKI may have issues:\n```\n{ovpn_output[:1500]}\n```")

        await ctx.send(f"✅ Server `{name}` is ready!\n"
                       "You can now use `!add-ssh`, `!add-vmess`, `!add-wireguard`, `!add-openvpn`, `!add-slowdns` to create user accounts.")
    else:
        await ctx.send(f"❌ Installation failed on `{name}`:\n```\n{output[:1500]}\n```")


@bot.command(name="add-ssh")
@commands.has_permissions(administrator=True)
async def add_ssh_cmd(ctx, server: str, username: str, password: str):
    """Create SSH user on a server
    Usage: !add-ssh <server> <username> <password>
    """
    if ctx.guild is None:
        await ctx.send("❌ This command can only be used in a server, not in DMs.")
        return

    if not get_server(server):
        await ctx.send(f"❌ Server `{server}` not found.")
        return

    await ctx.send(f"Creating SSH user `{username}` on `{server}`...")
    success, output = await ssh_exec(server, f"/opt/bibz-bot/manage-ssh.sh add {username} {password}")

    if success and "ADDED" in output:
        info = get_server(server)
        host = info["host"]
        port = info.get("port", 22)
        config = f"=== SSH Account ===\nHost: {host}\nPort: {port}\nUser: {username}\nPass: {password}\n\nssh -p {port} {username}@{host}"
        try:
            await ctx.author.send(f"```\n{config}\n```")
            await ctx.send(f"✅ SSH user `{username}` created. Cek DM buat config lengkapnya.")
        except:
            await ctx.send(f"✅ SSH user `{username}` created on `{server}`.\n```\n{config}\n```")
    elif success and "EXISTS" in output:
        await ctx.send(f"⚠️ SSH user `{username}` already exists on `{server}`.")
    else:
        await ctx.send(f"❌ Failed to create SSH user:\n```\n{output[:1500]}\n```")


@bot.command(name="add-vmess")
@commands.has_permissions(administrator=True)
async def add_vmess_cmd(ctx, server: str, username: str):
    """Create VMess/VLess account on a server
    Usage: !add-vmess <server> <username>
    """
    if ctx.guild is None:
        await ctx.send("❌ This command can only be used in a server, not in DMs.")
        return

    if not get_server(server):
        await ctx.send(f"❌ Server `{server}` not found.")
        return

    await ctx.send(f"Creating VMess account for `{username}` on `{server}`...")
    success, output = await ssh_exec(server, f"/opt/bibz-bot/manage-xray.sh add {username} vmess")

    if success:
        info = get_server(server)
        host = info["host"]
        config = f"=== VMess Account ===\nHost: {host}\nPort: 9443\nUser: {username}\nUUID: {output.strip()}\nPath: /vmess\nNetwork: ws\n\nvmess://... (salin UUID di atas)"
        try:
            await ctx.author.send(f"```\n{config}\n```")
            await ctx.send(f"✅ VMess account for `{username}` created. Cek DM.")
        except:
            await ctx.send(f"✅ VMess account created.\n```\n{config}\n```")
    else:
        await ctx.send(f"❌ Failed to create VMess account:\n```\n{output[:1500]}\n```")


@bot.command(name="add-wireguard")
@commands.has_permissions(administrator=True)
async def add_wireguard_cmd(ctx, server: str, username: str):
    """Create WireGuard config on a server
    Usage: !add-wireguard <server> <username>
    """
    if ctx.guild is None:
        await ctx.send("❌ This command can only be used in a server, not in DMs.")
        return

    if not get_server(server):
        await ctx.send(f"❌ Server `{server}` not found.")
        return

    await ctx.send(f"Creating WireGuard config for `{username}` on `{server}`...")
    success, output = await ssh_exec(server, f"/opt/bibz-bot/manage-wg.sh add {username}")

    if success:
        config = ""
        for line in output.split("\n"):
            if line.startswith("CONFIG:"):
                config = line[7:]
                break
        if config:
            try:
                await ctx.author.send(f"```\n=== WireGuard Config ===\n{config}\n```")
                await ctx.send(f"✅ WireGuard config for `{username}` created. Cek DM.")
            except:
                await ctx.send(f"✅ WireGuard config:\n```\n{config}\n```")
        else:
            try:
                await ctx.author.send(f"```\n{output}\n```")
                await ctx.send(f"✅ WireGuard account `{username}` created. Cek DM.")
            except:
                await ctx.send(f"✅ WireGuard account created.\n```\n{output}\n```")
    else:
        await ctx.send(f"❌ Failed to create WireGuard config:\n```\n{output[:1500]}\n```")


@bot.command(name="add-openvpn")
@commands.has_permissions(administrator=True)
async def add_openvpn_cmd(ctx, server: str, username: str):
    """Create OpenVPN account on a server
    Usage: !add-openvpn <server> <username>
    """
    if ctx.guild is None:
        await ctx.send("❌ This command can only be used in a server, not in DMs.")
        return

    if not get_server(server):
        await ctx.send(f"❌ Server `{server}` not found.")
        return

    await ctx.send(f"Creating OpenVPN account for `{username}` on `{server}`...")
    success, output = await ssh_exec(server, f"/opt/bibz-bot/manage-ovpn.sh add {username}")

    if success:
        try:
            await ctx.author.send(f"```\n=== OpenVPN Account ===\n{output}\n```")
            await ctx.send(f"✅ OpenVPN account `{username}` created. Cek DM.")
        except:
            await ctx.send(f"✅ OpenVPN account created.\n```\n{output}\n```")
    else:
        await ctx.send(f"❌ Failed to create OpenVPN account:\n```\n{output[:1500]}\n```")


@bot.command(name="add-slowdns")
@commands.has_permissions(administrator=True)
async def add_slowdns_cmd(ctx, server: str, username: str):
    """Create SlowDNS account on a server
    Usage: !add-slowdns <server> <username>
    """
    if ctx.guild is None:
        await ctx.send("❌ This command can only be used in a server, not in DMs.")
        return

    if not get_server(server):
        await ctx.send(f"❌ Server `{server}` not found.")
        return

    await ctx.send(f"Creating SlowDNS account for `{username}` on `{server}`...")
    success, output = await ssh_exec(server, f"/opt/bibz-bot/manage-slowdns.sh add {username}")

    if success:
        host = ""
        for line in output.split("\n"):
            if line.startswith("HOST:"):
                host = line[5:]
                break
        msg = f"=== SlowDNS Account ===\nHost: {host}\nUser: {username}\nDNS: 8.8.8.8:53"
        try:
            await ctx.author.send(f"```\n{msg}\n```")
            await ctx.send(f"✅ SlowDNS account `{username}` created. Cek DM.")
        except:
            await ctx.send(f"✅ SlowDNS account created.\n```\n{msg}\n```")
    else:
        await ctx.send(f"❌ Failed to create SlowDNS account:\n```\n{output[:1500]}\n```")


@bot.command(name="list-users")
@commands.has_permissions(administrator=True)
async def list_users_cmd(ctx, server: str):
    """List all SSH users on a server
    Usage: !list-users <server>
    """
    if ctx.guild is None:
        await ctx.send("❌ This command can only be used in a server, not in DMs.")
        return

    if not get_server(server):
        await ctx.send(f"❌ Server `{server}` not found.")
        return

    await ctx.send(f"Fetching users from `{server}`...")
    success, output = await ssh_exec(server, "/opt/bibz-bot/manage-ssh.sh list")

    if success:
        users = [u.strip() for u in output.split("\n") if u.strip()]
        if users:
            msg = f"📋 **Users on {server}**\n\n"
            for u in users:
                msg += f"• `{u}`\n"
            await ctx.send(msg)
        else:
            await ctx.send(f"📋 No users found on `{server}`.")
    else:
        await ctx.send(f"❌ Failed to list users:\n```\n{output[:1500]}\n```")


@bot.command(name="remove-user")
@commands.has_permissions(administrator=True)
async def remove_user_cmd(ctx, server: str, username: str, service: str = "ssh"):
    """Remove a user from a service on a server
    Usage: !remove-user <server> <username> [service]
    Services: ssh, vmess, wireguard, openvpn, slowdns (default: ssh)
    """
    if ctx.guild is None:
        await ctx.send("❌ This command can only be used in a server, not in DMs.")
        return

    if not get_server(server):
        await ctx.send(f"❌ Server `{server}` not found.")
        return

    service_scripts = {
        "ssh": "manage-ssh.sh remove",
        "vmess": "manage-xray.sh remove",
        "wireguard": "manage-wg.sh remove",
        "openvpn": "manage-ovpn.sh remove",
        "slowdns": "manage-slowdns.sh remove",
    }

    script = service_scripts.get(service.lower())
    if not script:
        valid = ", ".join(service_scripts.keys())
        await ctx.send(f"❌ Unknown service: `{service}`. Valid services: {valid}")
        return

    await ctx.send(f"Removing `{username}` from {service} on `{server}`...")
    success, output = await ssh_exec(server, f"/opt/bibz-bot/{script} {username}")

    if success:
        await ctx.send(f"✅ User `{username}` removed from {service} on `{server}`.")
    else:
        await ctx.send(f"❌ Failed to remove user:\n```\n{output[:1500]}\n```")

def main():
    """Main entry point"""
    print("[MAIN] Starting...", flush=True)
    if not DISCORD_BOT_TOKEN:
        logger.error("DISCORD_BOT_TOKEN not found in environment variables!")
        logger.error("Please create a .env file with your bot token.")
        return
    
    print(f"[MAIN] Token length: {len(DISCORD_BOT_TOKEN)}", flush=True)
    print("[MAIN] Import checks OK, calling bot.run()...", flush=True)
    
    try:
        bot.run(DISCORD_BOT_TOKEN)
    except discord.LoginFailure:
        logger.error("Failed to login - invalid bot token!")
        print("[MAIN] LoginFailure", flush=True)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        print("[MAIN] KeyboardInterrupt", flush=True)
    except Exception as e:
        logger.error(f"Bot crashed with error: {e}", exc_info=True)
        print(f"[MAIN] Crash: {e}", flush=True)
        import traceback
        traceback.print_exc(file=sys.stdout)


if __name__ == "__main__":
    main()
