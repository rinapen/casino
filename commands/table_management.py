"""
カジノテーブル管理コマンド
管理者専用のチャンネル作成・削除機能
"""
from typing import Optional

import discord
from discord import app_commands

from config import GUILD_ID
from database.db import (
    save_casino_table,
    get_all_casino_tables,
    delete_casino_table,
    clear_all_casino_tables,
    get_casino_table_count
)

# ========================================
# 定数
# ========================================
MAX_CHANNELS_PER_CATEGORY = 50  # Discordのカテゴリあたりの最大チャンネル数
BASE_CATEGORY_NAME = "Tables"
TABLE_CHANNEL_PREFIX = "Table-"


# ========================================
# ヘルパー関数
# ========================================
async def get_casino_categories(guild: discord.Guild) -> list[discord.CategoryChannel]:
    """カジノテーブルカテゴリを全て取得"""
    return [
        cat for cat in guild.categories
        if cat.name.startswith(BASE_CATEGORY_NAME)
    ]


async def create_category(guild: discord.Guild, number: int) -> discord.CategoryChannel:
    """
    新しいカジノテーブルカテゴリを作成（メッセージ送信のみ許可）
    
    Args:
        guild: Discordサーバー
        number: カテゴリ番号
    
    Returns:
        作成されたカテゴリ
    """
    category_name = f"{BASE_CATEGORY_NAME} #{number}" if number > 1 else BASE_CATEGORY_NAME
    
    # カテゴリレベルの権限設定（子チャンネルに継承される）
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            # 許可する権限
            view_channel=True,
            send_messages=True,
            read_messages=True,
            read_message_history=True,
            
            # 禁止する権限
            create_instant_invite=False,  # 招待リンク作成禁止
            manage_channels=False,
            manage_permissions=False,
            manage_webhooks=False,
            create_public_threads=False,
            create_private_threads=False,
            send_messages_in_threads=False,
            manage_messages=False,
            manage_threads=False,
            embed_links=False,
            attach_files=False,
            add_reactions=False,
            use_external_emojis=False,
            use_external_stickers=False,
            mention_everyone=False,
            use_application_commands=False
        )
    }
    
    return await guild.create_category(category_name, overwrites=overwrites)


async def create_table_channel(
    category: discord.CategoryChannel,
    table_number: int
) -> discord.TextChannel:
    """
    テーブルチャンネルを作成（メッセージ送信のみ許可）
    
    Args:
        category: 作成先のカテゴリ
        table_number: テーブル番号
    
    Returns:
        作成されたテキストチャンネル
    """
    channel_name = f"{TABLE_CHANNEL_PREFIX}{table_number:03d}"  # table-001, table-002, ...
    
    # 権限設定: メッセージ送信のみ許可、その他は禁止
    overwrites = {
        category.guild.default_role: discord.PermissionOverwrite(
            # 許可する権限
            send_messages=True,
            read_messages=True,
            read_message_history=True,
            
            # 禁止する権限
            create_instant_invite=False,  # 招待リンク作成禁止
            manage_channels=False,
            manage_permissions=False,
            manage_webhooks=False,
            create_public_threads=False,
            create_private_threads=False,
            send_messages_in_threads=False,
            manage_messages=False,
            manage_threads=False,
            embed_links=False,
            attach_files=False,
            add_reactions=False,
            use_external_emojis=False,
            use_external_stickers=False,
            mention_everyone=False,
            use_application_commands=False
        )
    }
    
    return await category.create_text_channel(
        channel_name,
        overwrites=overwrites,
        topic=f"カジノテーブル #{table_number}"
    )


# ========================================
# スラッシュコマンド
# ========================================
async def setup_table_commands(bot):
    """テーブル管理コマンドを登録"""
    
    @bot.tree.command(name="テーブル作成", description="指定した数のカジノテーブルチャンネルを作成（管理者専用）")
    @app_commands.describe(count="作成するテーブル数")
    async def create_tables(interaction: discord.Interaction, count: int):
        """
        カジノテーブルを作成
        
        Args:
            interaction: Discord Interaction
            count: 作成するテーブル数
        """
        # 管理者権限チェック
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "このコマンドは管理者のみ実行できます。",
                ephemeral=True
            )
            return
        
        # 入力値チェック
        if count <= 0:
            await interaction.response.send_message(
                "テーブル数は1以上を指定してください。",
                ephemeral=True
            )
            return
        
        if count > 500:
            await interaction.response.send_message(
                "一度に作成できるテーブル数は500までです。",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # 進捗報告用のメッセージを送信
        progress_embed = discord.Embed(
            title="テーブル作成中...",
            description=f"0/{count} テーブル作成完了",
            color=discord.Color.blue()
        )
        progress_message = await interaction.followup.send(embed=progress_embed, ephemeral=True)
        
        try:
            guild = interaction.guild
            
            # データベースから既存のテーブル数を取得
            existing_tables = get_casino_table_count()
            
            # 既存のカジノカテゴリを取得
            categories = await get_casino_categories(guild)
            
            # 現在のカテゴリまたは新しいカテゴリを取得
            if not categories:
                current_category = await create_category(guild, 1)
                categories = [current_category]
                category_number = 1
            else:
                # 最後のカテゴリを使用
                current_category = categories[-1]
                category_number = len(categories)
                
                # 最後のカテゴリがいっぱいなら新しいカテゴリを作成
                if len(current_category.channels) >= MAX_CHANNELS_PER_CATEGORY:
                    category_number += 1
                    current_category = await create_category(guild, category_number)
                    categories.append(current_category)
            
            created_channels = []
            
            for i in range(count):
                table_number = existing_tables + i + 1
                
                # 現在のカテゴリがいっぱいか確認
                if len(current_category.channels) >= MAX_CHANNELS_PER_CATEGORY:
                    category_number += 1
                    current_category = await create_category(guild, category_number)
                    categories.append(current_category)
                
                # チャンネル作成
                channel = await create_table_channel(current_category, table_number)
                created_channels.append(channel)
                
                # データベースに保存
                save_casino_table(
                    channel_id=channel.id,
                    category_id=current_category.id,
                    table_number=table_number,
                    channel_name=channel.name,
                    category_name=current_category.name
                )
                
                # 進捗報告（5件ごとに編集更新）
                if (i + 1) % 5 == 0 or (i + 1) == count:
                    progress_percentage = ((i + 1) / count) * 100
                    progress_bar = "█" * int(progress_percentage / 5) + "░" * (20 - int(progress_percentage / 5))
                    
                    progress_embed.description = (
                        f"**{i + 1}/{count}** テーブル作成完了\n"
                        f"`{progress_bar}` {progress_percentage:.1f}%\n\n"
                        f"最新: `{channel.name}` in `{current_category.name}`"
                    )
                    await progress_message.edit(embed=progress_embed)
            
            # 完了報告（進捗メッセージを編集）
            progress_embed.title = "✅ テーブル作成完了"
            progress_embed.description = f"**{count}個**のテーブルを作成しました。"
            progress_embed.color = discord.Color.green()
            progress_embed.clear_fields()
            
            progress_embed.add_field(
                name="作成されたテーブル",
                value=f"`{TABLE_CHANNEL_PREFIX}{existing_tables + 1:03d}` ～ `{TABLE_CHANNEL_PREFIX}{existing_tables + count:03d}`",
                inline=False
            )
            progress_embed.add_field(
                name="使用カテゴリ数",
                value=f"{len(categories)}個",
                inline=False
            )
            progress_embed.add_field(
                name="データベース登録",
                value=f"{count}件のテーブル情報を保存",
                inline=False
            )
            progress_embed.set_footer(text="権限設定: メッセージ送信のみ許可、招待リンク作成禁止")
            
            await progress_message.edit(embed=progress_embed)
            
        except discord.Forbidden:
            progress_embed.title = "❌ エラー"
            progress_embed.description = "権限不足でチャンネル/カテゴリを作成できませんでした。"
            progress_embed.color = discord.Color.red()
            await progress_message.edit(embed=progress_embed)
        except Exception as e:
            progress_embed.title = "❌ エラー"
            progress_embed.description = f"エラーが発生しました:\n```{type(e).__name__}: {str(e)}```"
            progress_embed.color = discord.Color.red()
            await progress_message.edit(embed=progress_embed)
    
    @bot.tree.command(name="テーブル削除", description="全てのカジノテーブルチャンネルを削除（管理者専用）")
    @app_commands.describe(confirm="削除を確認するため 'delete' と入力")
    async def delete_tables(interaction: discord.Interaction, confirm: str):
        """
        全カジノテーブルを削除
        
        Args:
            interaction: Discord Interaction
            confirm: 確認文字列（"delete"）
        """
        # 管理者権限チェック
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "このコマンドは管理者のみ実行できます。",
                ephemeral=True
            )
            return
        
        # 確認文字列チェック
        if confirm.lower() != "delete":
            await interaction.response.send_message(
                "削除を実行するには `delete` と正確に入力してください。",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # 進捗報告用のメッセージを送信
        progress_embed = discord.Embed(
            title="テーブル削除中...",
            description="準備中...",
            color=discord.Color.orange()
        )
        progress_message = await interaction.followup.send(embed=progress_embed, ephemeral=True)
        
        try:
            guild = interaction.guild
            
            # データベースから全テーブル情報を取得
            all_tables = get_all_casino_tables()
            
            if not all_tables:
                progress_embed.title = "削除対象なし"
                progress_embed.description = "削除対象のカジノテーブルがデータベースに見つかりませんでした。"
                progress_embed.color = discord.Color.yellow()
                await progress_message.edit(embed=progress_embed)
                return
            
            total_tables = len(all_tables)
            deleted_channels = 0
            deleted_categories_set = set()
            failed_channels = []
            
            # データベースに保存されているテーブルを削除
            for idx, table_info in enumerate(all_tables):
                channel_id = table_info.get("channel_id")
                category_id = table_info.get("category_id")
                channel_name = table_info.get("channel_name", "不明")
                
                try:
                    # チャンネルを取得して削除
                    channel = guild.get_channel(channel_id)
                    
                    if channel:
                        await channel.delete(reason=f"管理者 {interaction.user.name} による一括削除")
                        deleted_channels += 1
                        deleted_categories_set.add(category_id)
                    else:
                        # チャンネルが既に存在しない場合
                        failed_channels.append(f"{channel_name} (ID: {channel_id}) - 既に削除済み")
                    
                    # データベースから削除
                    delete_casino_table(channel_id)
                    
                except discord.Forbidden:
                    failed_channels.append(f"{channel_name} - 権限不足")
                except Exception as e:
                    failed_channels.append(f"{channel_name} - エラー: {e}")
                
                # 進捗報告（5件ごとまたは最後に編集更新）
                if (idx + 1) % 5 == 0 or (idx + 1) == total_tables:
                    progress_percentage = ((idx + 1) / total_tables) * 100
                    progress_bar = "█" * int(progress_percentage / 5) + "░" * (20 - int(progress_percentage / 5))
                    
                    progress_embed.description = (
                        f"**{idx + 1}/{total_tables}** テーブル処理完了\n"
                        f"`{progress_bar}` {progress_percentage:.1f}%\n\n"
                        f"削除成功: {deleted_channels}件\n"
                        f"失敗/スキップ: {len(failed_channels)}件"
                    )
                    await progress_message.edit(embed=progress_embed)
            
            # 空のカテゴリを削除
            progress_embed.description += "\n\nカテゴリをクリーンアップ中..."
            await progress_message.edit(embed=progress_embed)
            
            deleted_categories = 0
            for category_id in deleted_categories_set:
                try:
                    category = guild.get_channel(category_id)
                    if category and len(category.channels) == 0:
                        await category.delete(reason=f"管理者 {interaction.user.name} による空カテゴリ削除")
                        deleted_categories += 1
                except Exception as e:
                    failed_channels.append(f"カテゴリ削除エラー: {e}")
            
            # 完了報告（進捗メッセージを編集）
            progress_embed.title = "✅ テーブル削除完了"
            progress_embed.color = discord.Color.red()
            progress_embed.clear_fields()
            
            progress_embed.add_field(
                name="削除されたチャンネル",
                value=f"{deleted_channels}個",
                inline=True
            )
            progress_embed.add_field(
                name="削除されたカテゴリ",
                value=f"{deleted_categories}個",
                inline=True
            )
            
            if failed_channels:
                failed_list = "\n".join(failed_channels[:10])  # 最大10件表示
                if len(failed_channels) > 10:
                    failed_list += f"\n... 他 {len(failed_channels) - 10}件"
                progress_embed.add_field(
                    name="削除失敗/スキップ",
                    value=f"```{failed_list}```",
                    inline=False
                )
            
            progress_embed.set_footer(text="データベースからも削除されました")
            
            await progress_message.edit(embed=progress_embed)
            
        except Exception as e:
            progress_embed.title = "❌ エラー"
            progress_embed.description = f"削除処理中にエラーが発生しました:\n```{type(e).__name__}: {str(e)}```"
            progress_embed.color = discord.Color.red()
            await progress_message.edit(embed=progress_embed)
    
    @bot.tree.command(name="テーブル一覧", description="登録されているカジノテーブルの一覧を表示（管理者専用）")
    async def list_tables(interaction: discord.Interaction):
        """
        全カジノテーブルの一覧を表示
        
        Args:
            interaction: Discord Interaction
        """
        # 管理者権限チェック
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "このコマンドは管理者のみ実行できます。",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # データベースから全テーブル情報を取得
            all_tables = get_all_casino_tables()
            
            if not all_tables:
                await interaction.followup.send(
                    "登録されているカジノテーブルはありません。",
                    ephemeral=True
                )
                return
            
            guild = interaction.guild
            
            # カテゴリごとにグループ化
            categories_dict = {}
            active_count = 0
            deleted_count = 0
            
            for table_info in all_tables:
                channel_id = table_info.get("channel_id")
                category_name = table_info.get("category_name", "不明")
                channel_name = table_info.get("channel_name", "不明")
                
                # チャンネルが存在するかチェック
                channel = guild.get_channel(channel_id)
                status = "🟢" if channel else "🔴削除済み"
                
                if channel:
                    active_count += 1
                else:
                    deleted_count += 1
                
                if category_name not in categories_dict:
                    categories_dict[category_name] = []
                
                categories_dict[category_name].append(f"{status} {channel_name}")
            
            # Embed作成
            embed = discord.Embed(
                title="カジノテーブル一覧",
                description=f"**総登録数:** {len(all_tables)}件\n**アクティブ:** {active_count}件 | **削除済み:** {deleted_count}件",
                color=discord.Color.blue()
            )
            
            # カテゴリごとに表示（最大25フィールド）
            field_count = 0
            for category_name, channels in sorted(categories_dict.items()):
                if field_count >= 25:
                    embed.add_field(
                        name="...",
                        value=f"残り {len(categories_dict) - field_count}カテゴリ",
                        inline=False
                    )
                    break
                
                channel_list = "\n".join(channels[:20])  # カテゴリあたり最大20件
                if len(channels) > 20:
                    channel_list += f"\n... 他 {len(channels) - 20}件"
                
                embed.add_field(
                    name=f"📁 {category_name}",
                    value=channel_list,
                    inline=False
                )
                field_count += 1
            
            embed.set_footer(text="🟢=アクティブ | 🔴=削除済み（DB上のみ存在）")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"一覧取得中にエラーが発生しました: `{type(e).__name__}: {str(e)}`",
                ephemeral=True
            )

