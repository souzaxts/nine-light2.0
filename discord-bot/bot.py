#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Discord com Sistema de Painel de Controle
Autor: Assistente Claude
Versão: 1.1 - Corrigida
"""

import discord
from discord.ext import commands
from datetime import datetime
import logging
import json
import os
import asyncio

# Carregar variáveis do arquivo .env se existir
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("📁 Arquivo .env carregado")
except ImportError:
    print("⚠️  python-dotenv não instalado, usando apenas variáveis do sistema")

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)

class BotConfig:
    """Gerenciador de configurações por servidor"""
    
    def __init__(self, guild_id):
        self.guild_id = guild_id
        self.config_file = f"configs/config_{guild_id}.json"
        self.default_config = {
            "ban_function": True,
            "welcome_messages": True,
            "auto_moderation": False,
            "logs": True,
            "dm_notifications": True,
            "anti_spam": False,
            "auto_role": False
        }
        self.config = {}
        self.ensure_config_dir()
        self.load_config()
    
    def ensure_config_dir(self):
        """Cria diretório de configurações se não existir"""
        if not os.path.exists('configs'):
            os.makedirs('configs')
    
    def load_config(self):
        """Carrega configurações do arquivo"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                # Adicionar novas configurações se não existirem
                for key, value in self.default_config.items():
                    if key not in self.config:
                        self.config[key] = value
                self.save_config()
            else:
                self.config = self.default_config.copy()
                self.save_config()
        except Exception as e:
            logging.error(f"Erro ao carregar config para guild {self.guild_id}: {e}")
            self.config = self.default_config.copy()
    
    def save_config(self):
        """Salva configurações no arquivo"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Erro ao salvar config para guild {self.guild_id}: {e}")
    
    def toggle_function(self, function_name):
        """Alterna estado de uma função"""
        if function_name in self.config:
            self.config[function_name] = not self.config[function_name]
            self.save_config()
            return self.config[function_name]
        return None
    
    def is_enabled(self, function_name):
        """Verifica se função está ativa"""
        return self.config.get(function_name, False)
    
    def get_status_summary(self):
        """Retorna resumo do status das funções"""
        active = sum(1 for v in self.config.values() if v)
        total = len(self.config)
        return f"{active}/{total} funções ativas"

class ControlPanelView(discord.ui.View):
    """Interface do painel de controle"""
    
    def __init__(self, bot_config, user_id, bot):
        super().__init__(timeout=300)
        self.bot_config = bot_config
        self.user_id = user_id
        self.bot = bot
        self.update_buttons()
    
    def update_buttons(self):
        """Atualiza botões baseado no estado atual"""
        self.clear_items()
        
        # Definição das funções disponíveis
        functions = [
            ("ban_function", "🔨 Sistema de Ban", "Sistema de banimento com mensagens"),
            ("welcome_messages", "👋 Boas-vindas", "Mensagens para novos membros"),
            ("auto_moderation", "🛡️ Auto Moderação", "Moderação automática de conteúdo"),
            ("logs", "📋 Logs", "Sistema de registro de eventos"),
            ("dm_notifications", "💬 DM Notificações", "Notificar usuários por DM"),
            ("anti_spam", "🚫 Anti-Spam", "Proteção contra spam"),
            ("auto_role", "🎭 Auto Role", "Cargo automático para novos membros")
        ]
        
        # Criar botões para cada função
        for func_key, label, description in functions:
            is_enabled = self.bot_config.is_enabled(func_key)
            style = discord.ButtonStyle.success if is_enabled else discord.ButtonStyle.danger
            emoji = "✅" if is_enabled else "❌"
            
            button = discord.ui.Button(
                label=f"{emoji} {label}",
                style=style,
                custom_id=func_key,
                row=len(self.children) // 5  # Organizar em linhas
            )
            button.callback = self.create_toggle_callback(func_key)
            self.add_item(button)
        
        # Botões de controle
        info_button = discord.ui.Button(
            label="📊 Status Detalhado",
            style=discord.ButtonStyle.primary,
            custom_id="detailed_status"
        )
        info_button.callback = self.show_detailed_status
        self.add_item(info_button)
        
        refresh_button = discord.ui.Button(
            label="🔄 Atualizar",
            style=discord.ButtonStyle.secondary,
            custom_id="refresh"
        )
        refresh_button.callback = self.refresh_panel
        self.add_item(refresh_button)
        
        close_button = discord.ui.Button(
            label="🔒 Fechar",
            style=discord.ButtonStyle.secondary,
            custom_id="close"
        )
        close_button.callback = self.close_panel
        self.add_item(close_button)
    
    def create_toggle_callback(self, function_name):
        """Cria callback para alternar função específica"""
        async def callback(interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message(
                    "❌ Apenas quem abriu o painel pode controlá-lo!", 
                    ephemeral=True
                )
                return
            
            new_state = self.bot_config.toggle_function(function_name)
            status_text = "**Ativado** ✅" if new_state else "**Desativado** ❌"
            func_display = function_name.replace('_', ' ').title()
            
            self.update_buttons()
            embed = self.create_main_embed()
            
            await interaction.response.edit_message(embed=embed, view=self)
            
            # Feedback do usuário
            await interaction.followup.send(
                f"🔧 **{func_display}** foi {status_text}", 
                ephemeral=True
            )
        
        return callback
    
    async def show_detailed_status(self, interaction):
        """Mostra status detalhado de todas as funções"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ Apenas quem abriu o painel pode ver detalhes!", 
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="📊 Status Detalhado das Funções",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        functions_info = {
            "ban_function": ("🔨 Sistema de Ban", "Permite banir usuários com mensagens personalizadas"),
            "welcome_messages": ("👋 Mensagens de Boas-vindas", "Envia mensagens automáticas para novos membros"),
            "auto_moderation": ("🛡️ Auto Moderação", "Remove mensagens inadequadas automaticamente"),
            "logs": ("📋 Sistema de Logs", "Registra todas as ações do bot em arquivo"),
            "dm_notifications": ("💬 Notificações DM", "Envia DMs para usuários afetados por ações"),
            "anti_spam": ("🚫 Anti-Spam", "Detecta e remove mensagens de spam"),
            "auto_role": ("🎭 Auto Role", "Atribui cargo automaticamente para novos membros")
        }
        
        status_text = ""
        for func_key, (name, desc) in functions_info.items():
            status = "🟢 Ativo" if self.bot_config.is_enabled(func_key) else "🔴 Inativo"
            status_text += f"**{name}**\n{desc}\nStatus: {status}\n\n"
        
        embed.description = status_text
        embed.set_footer(text=f"Guild ID: {self.bot_config.guild_id}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def refresh_panel(self, interaction):
        """Atualiza o painel"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ Apenas quem abriu o painel pode atualizá-lo!", 
                ephemeral=True
            )
            return
        
        self.bot_config.load_config()  # Recarregar do arquivo
        self.update_buttons()
        embed = self.create_main_embed()
        
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send("🔄 Painel atualizado!", ephemeral=True)
    
    async def close_panel(self, interaction):
        """Fecha o painel de controle"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ Apenas quem abriu o painel pode fechá-lo!", 
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="🔒 Painel de Controle Fechado",
            description="O painel foi fechado com sucesso!\nUse `!painel` para abrir novamente.",
            color=discord.Color.gray(),
            timestamp=datetime.now()
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()
    
    def create_main_embed(self):
        """Cria embed principal do painel"""
        embed = discord.Embed(
            title="🤖 Painel de Controle do Bot",
            description="Clique nos botões para ativar/desativar funções do bot",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        # Status resumido
        status_summary = self.bot_config.get_status_summary()
        embed.add_field(
            name="📈 Resumo",
            value=f"**Status:** {status_summary}",
            inline=False
        )
        
        # Instruções
        embed.add_field(
            name="ℹ️ Instruções",
            value="• ✅ = Função Ativa\n• ❌ = Função Inativa\n• Clique para alternar",
            inline=True
        )
        
        # Verificar se usuário existe antes de tentar mencionar
        try:
            user_mention = self.bot.get_user(self.user_id).mention if self.bot.get_user(self.user_id) else "Usuário Desconhecido"
        except:
            user_mention = "Usuário Desconhecido"
        
        embed.add_field(
            name="⏰ Informações",
            value=f"• Painel expira em 5 min\n• Usuário: {user_mention}",
            inline=True
        )
        
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(
            text="Bot desenvolvido com discord.py",
            icon_url=self.bot.user.display_avatar.url
        )
        
        return embed
    
    async def on_timeout(self):
        """Executado quando o painel expira"""
        try:
            embed = discord.Embed(
                title="⏰ Painel Expirado",
                description="O painel expirou após 5 minutos de inatividade.\nUse `!painel` para abrir um novo.",
                color=discord.Color.orange()
            )
            # Note: message object precisa ser armazenado para funcionar
        except:
            pass
        self.clear_items()

class ModerationCog(commands.Cog):
    """Cog principal de moderação"""
    
    def __init__(self, bot):
        self.bot = bot
        self.configs = {}
    
    def get_config(self, guild_id):
        """Obtém ou cria configuração para um servidor"""
        if guild_id not in self.configs:
            self.configs[guild_id] = BotConfig(guild_id)
        return self.configs[guild_id]
    
    @commands.command(name='painel', aliases=['controle', 'config', 'configurar', 'settings'])
    @commands.has_permissions(administrator=True)
    async def control_panel(self, ctx):
        """
        🎛️ Abre o painel de controle do bot
        
        **Uso:** `!painel`
        **Permissão:** Administrador
        **Aliases:** controle, config, configurar, settings
        """
        config = self.get_config(ctx.guild.id)
        view = ControlPanelView(config, ctx.author.id, self.bot)
        embed = view.create_main_embed()
        
        message = await ctx.send(embed=embed, view=view)
        
        # Log da ação
        if config.is_enabled("logs"):
            logging.info(f"Painel aberto por {ctx.author} no servidor {ctx.guild.name}")
    
    @discord.app_commands.command(name="painel", description="Abre o painel de controle do bot")
    async def control_panel_slash(self, interaction: discord.Interaction):
        """Comando slash para o painel"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ **Acesso Negado!**\nVocê precisa ter permissão de **Administrador** para usar este comando.", 
                ephemeral=True
            )
            return
        
        config = self.get_config(interaction.guild.id)
        view = ControlPanelView(config, interaction.user.id, self.bot)
        embed = view.create_main_embed()
        
        await interaction.response.send_message(embed=embed, view=view)
        
        # Log da ação
        if config.is_enabled("logs"):
            logging.info(f"Painel (slash) aberto por {interaction.user} no servidor {interaction.guild.name}")
    
    async def ban_with_welcome(self, ctx, target_user: discord.Member, reason: str = "Não especificado"):
        """Sistema de ban com verificação de configuração"""
        config = self.get_config(ctx.guild.id)
        
        # Verificar se função está ativa
        if not config.is_enabled("ban_function"):
            embed = discord.Embed(
                title="❌ Função Desativada",
                description="O sistema de ban está **desativado**!\nUse `!painel` para ativar esta função.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return False
        
        try:
            # Verificações de segurança
            checks = [
                (not ctx.author.guild_permissions.ban_members, "❌ Você não tem permissão para banir membros!"),
                (not ctx.guild.me.guild_permissions.ban_members, "❌ Eu não tenho permissão para banir membros!"),
                (target_user.id == ctx.author.id, "❌ Você não pode banir a si mesmo!"),
                (target_user.id == self.bot.user.id, "❌ Não posso banir a mim mesmo!"),
                (target_user.top_role >= ctx.author.top_role, "❌ Você não pode banir alguém com cargo igual ou superior!"),
                (target_user.top_role >= ctx.guild.me.top_role, "❌ Não posso banir alguém com cargo igual ou superior ao meu!")
            ]
            
            for condition, message in checks:
                if condition:
                    await ctx.send(message)
                    return False
            
            # Criar embed de boas-vindas irônico
            welcome_embed = discord.Embed(
                title="🎉 Bem-vindo(a) ao Ban! 🎉",
                description=f"**{target_user.display_name}** foi cordialmente convidado(a) a se retirar do servidor! 🚪",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            
            welcome_embed.add_field(
                name="👤 Usuário Banido", 
                value=f"{target_user.mention}\n`{target_user} ({target_user.id})`", 
                inline=True
            )
            welcome_embed.add_field(
                name="👮 Moderador", 
                value=f"{ctx.author.mention}\n`{ctx.author}`", 
                inline=True
            )
            welcome_embed.add_field(
                name="📋 Motivo", 
                value=f"```{reason}```", 
                inline=False
            )
            welcome_embed.add_field(
                name="📅 Data & Hora", 
                value=f"<t:{int(datetime.now().timestamp())}:F>", 
                inline=False
            )
            
            welcome_embed.set_thumbnail(url=target_user.display_avatar.url)
            welcome_embed.set_footer(
                text="🚪 Obrigado por 'visitar' nosso servidor! Volte sempre... ou não! 😄",
                icon_url=ctx.guild.icon.url if ctx.guild.icon else None
            )
            
            # Enviar DM se ativado
            if config.is_enabled("dm_notifications"):
                try:
                    dm_embed = discord.Embed(
                        title="🔨 Você foi banido!",
                        description=f"Você foi banido do servidor **{ctx.guild.name}**",
                        color=discord.Color.red(),
                        timestamp=datetime.now()
                    )
                    
                    dm_embed.add_field(name="📋 Motivo", value=reason, inline=False)
                    dm_embed.add_field(name="👮 Moderador", value=str(ctx.author), inline=False)
                    dm_embed.add_field(name="📅 Data", value=f"<t:{int(datetime.now().timestamp())}:F>", inline=False)
                    dm_embed.set_footer(text="Se você acredita que este banimento foi injusto, entre em contato com a administração do servidor.")
                    
                    await target_user.send(embed=dm_embed)
                except discord.Forbidden:
                    if config.is_enabled("logs"):
                        logging.warning(f"Não foi possível enviar DM para {target_user}")
            
            # Executar ban
            ban_reason = f"{reason} | Banido por: {ctx.author} | ID: {ctx.author.id}"
            await target_user.ban(reason=ban_reason, delete_message_days=1)
            
            # Enviar resposta
            await ctx.send(embed=welcome_embed)
            
            # Log se ativado
            if config.is_enabled("logs"):
                logging.info(f"BAN: {target_user} ({target_user.id}) banido de {ctx.guild.name} por {ctx.author}. Motivo: {reason}")
            
            return True
            
        except discord.Forbidden:
            await ctx.send("❌ Não tenho permissão para banir este usuário!")
            return False
        except discord.HTTPException as e:
            await ctx.send(f"❌ Erro ao banir usuário: {e}")
            return False
        except Exception as e:
            if config.is_enabled("logs"):
                logging.error(f"Erro inesperado no ban: {e}")
            await ctx.send("❌ Ocorreu um erro inesperado!")
            return False
    
    @commands.command(name='ban', aliases=['banir'])
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban_command(self, ctx, member: discord.Member, *, reason: str = "Não especificado"):
        """
        🔨 Bane um usuário do servidor
        
        **Uso:** `!ban @usuario [motivo]`
        **Permissão:** Ban Members
        **Exemplo:** `!ban @Spammer Enviando links maliciosos`
        """
        await self.ban_with_welcome(ctx, member, reason)
    
    @discord.app_commands.command(name="ban", description="Bane um usuário do servidor")
    @discord.app_commands.describe(
        usuario="O usuário a ser banido",
        motivo="Motivo do banimento (opcional)"
    )
    async def ban_slash(self, interaction: discord.Interaction, usuario: discord.Member, motivo: str = "Não especificado"):
        """Comando slash para banir"""
        # Verificar permissões
        if not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message(
                "❌ Você não tem permissão para banir membros!", 
                ephemeral=True
            )
            return
        
        # Criar contexto fake para reutilizar função
        class FakeContext:
            def __init__(self, interaction):
                self.author = interaction.user
                self.guild = interaction.guild
                self.send = interaction.response.send_message
        
        fake_ctx = FakeContext(interaction)
        await self.ban_with_welcome(fake_ctx, usuario, motivo)
    
    @commands.command(name='info', aliases=['status', 'about'])
    async def info_command(self, ctx):
        """
        📊 Mostra informações sobre o bot
        """
        config = self.get_config(ctx.guild.id)
        
        embed = discord.Embed(
            title="🤖 Informações do Bot",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="📈 Status Geral",
            value=f"**Online:** ✅\n**Latência:** {round(self.bot.latency * 1000)}ms\n**Funções:** {config.get_status_summary()}",
            inline=True
        )
        
        embed.add_field(
            name="🔧 Comandos Principais",
            value="• `!painel` - Painel de controle\n• `!ban` - Banir usuário\n• `!info` - Informações",
            inline=True
        )
        
        embed.add_field(
            name="📚 Biblioteca",
            value=f"**discord.py** v{discord.__version__}\n**Python** 3.8+",
            inline=False
        )
        
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"Solicitado por {ctx.author}", icon_url=ctx.author.display_avatar.url)
        
        await ctx.send(embed=embed)
    
    @control_panel.error
    async def control_panel_error(self, ctx, error):
        """Handler de erros para comando painel"""
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Acesso Negado",
                description="Você precisa ter permissão de **Administrador** para usar este comando!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
    
    @ban_command.error
    async def ban_error(self, ctx, error):
        """Handler de erros para comando de ban"""
        config = self.get_config(ctx.guild.id)
        
        error_messages = {
            commands.MissingPermissions: "❌ Você não tem permissão para usar este comando!",
            commands.BotMissingPermissions: "❌ Eu não tenho permissão para banir membros!",
            commands.MemberNotFound: "❌ Usuário não encontrado no servidor!",
            commands.BadArgument: "❌ Usuário inválido! Use `!ban @usuario motivo`"
        }
        
        message = error_messages.get(type(error), "❌ Ocorreu um erro desconhecido!")
        await ctx.send(message)
        
        if config.is_enabled("logs"):
            logging.error(f"Erro no comando ban: {error}")

async def setup(bot):
    """Função para carregar a cog"""
    await bot.add_cog(ModerationCog(bot))

def main():
    """Função principal do bot"""
    # Configuração do bot
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.guilds = True
    
    bot = commands.Bot(
        command_prefix=['!', '?', '.'],
        intents=intents,
        help_command=None,
        case_insensitive=True
    )
    
    @bot.event
    async def on_ready():
        """Executado quando bot fica online"""
        print(f"""
╔══════════════════════════════════════╗
║            BOT ONLINE! ✅            ║
╠══════════════════════════════════════╣
║ Nome: {bot.user.name:<27} ║
║ ID: {bot.user.id:<29} ║
║ Servidores: {len(bot.guilds):<22} ║
╠══════════════════════════════════════╣
║           COMANDOS PRINCIPAIS        ║
╠══════════════════════════════════════╣
║ !painel - Abrir painel de controle   ║
║ !ban    - Banir usuário              ║
║ !info   - Informações do bot         ║
╚══════════════════════════════════════╝
        """)
        
        # Sincronizar comandos slash
        try:
            synced = await bot.tree.sync()
            print(f"✅ {len(synced)} comandos slash sincronizados")
        except Exception as e:
            print(f"❌ Erro ao sincronizar comandos: {e}")
        
        # Definir status do bot
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="!painel para configurar"
        )
        await bot.change_presence(status=discord.Status.online, activity=activity)
    
    @bot.event
    async def on_guild_join(guild):
        """Executado quando bot entra em um servidor"""
        print(f"📥 Entrei no servidor: {guild.name} (ID: {guild.id})")
        logging.info(f"Bot adicionado ao servidor {guild.name} ({guild.id})")
    
    @bot.event
    async def on_guild_remove(guild):
        """Executado quando bot sai de um servidor"""
        print(f"📤 Saí do servidor: {guild.name} (ID: {guild.id})")
        logging.info(f"Bot removido do servidor {guild.name} ({guild.id})")
    
    @bot.event
    async def on_command_error(ctx, error):
        """Handler global de erros"""
        if isinstance(error, commands.CommandNotFound):
            return  # Ignorar comandos não encontrados
        
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Sem Permissão",
                description="Você não tem permissão para usar este comando!",
                color=discord.Color.red()
            )
            try:
                await ctx.send(embed=embed, delete_after=10)
            except:
                pass
            return
        
        error_embed = discord.Embed(
            title="❌ Erro",
            description=str(error),
            color=discord.Color.red()
        )
        
        try:
            await ctx.send(embed=error_embed, delete_after=10)
        except:
            pass
        
        logging.error(f"Erro em comando: {error}")
    
    async def setup_hook():
        """Configuração inicial do bot"""
        await bot.add_cog(ModerationCog(bot))
        print("🔧 Cogs carregadas com sucesso!")
    
    # Definir setup_hook no bot
    bot.setup_hook = setup_hook
    
    # CORREÇÃO CRÍTICA: Usar variável de ambiente corretamente
    token = os.getenv('DISCORD_TOKEN')
    
    # DEBUG: Verificar se o .env foi carregado
    if not token:
        print("🔍 Tentando métodos alternativos...")
        # Tentar ler diretamente do arquivo .env
        try:
            with open('.env', 'r') as f:
                for line in f:
                    if line.startswith('DISCORD_TOKEN=MTQwNjc3ODc0NTMyMjQ3MTQ5NQ.GtG8Fv.jNr0vjrGpwM0CrV1oGvpzvf5N-ZfHvMUydWc7E'):
                        token = line.split('=', 1)[1].strip()
                        print("✅ Token encontrado no arquivo .env")
                        break
        except FileNotFoundError:
            print("❌ Arquivo .env não encontrado!")
        except Exception as e:
            print(f"❌ Erro ao ler .env: {e}")
    
    if not token:
        print("❌ ERRO: Token do Discord não encontrado!")
        print("📝 Defina a variável de ambiente DISCORD_TOKEN")
        print("🔗 Exemplo: export DISCORD_TOKEN=seu_token_aqui")
        print("💡 Ou crie um arquivo .env com: DISCORD_TOKEN=seu_token_aqui")
        return
    
    # Iniciar bot
    try:
        bot.run(token)
    except discord.LoginFailure:
        print("❌ ERRO: Token inválido!")
    except Exception as e:
        print(f"❌ ERRO FATAL: {e}")

if __name__ == "__main__":
    main()