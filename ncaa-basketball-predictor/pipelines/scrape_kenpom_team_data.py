"""
Complete KenPom Team Data Scraper

Scrapes ALL team-level statistics from KenPom:
- Efficiency ratings (tempo, offensive/defensive efficiency)
- Four Factors (eFG%, TO%, OR%, FTRate)
- Height/Experience data
- Team stats (3P%, 2P%, FT%, block%, steal%, etc.)

Complements the player scraper to get ALL possible data from KenPom.
"""

import sqlite3
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional
from tqdm import tqdm
import os
from dotenv import load_dotenv
import pandas as pd
from kenpompy.utils import login
from kenpompy import summary, misc

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "ncaa_basketball.db"


class KenPomTeamDataScraper:
    """Scrapes all team-level statistics from KenPom"""
    
    def __init__(
        self,
        db_path: Path = DB_PATH,
        email: Optional[str] = None,
        password: Optional[str] = None,
        rate_limit_seconds: float = 3.0
    ):
        self.db_path = db_path
        self.email = email or os.getenv('KENPOM_EMAIL')
        self.password = password or os.getenv('KENPOM_PASSWORD')
        self.rate_limit = rate_limit_seconds
        self.browser = None
        self.conn = None
        
        if not self.email or not self.password:
            raise ValueError("❌ KenPom email and password required")
    
    def __enter__(self):
        """Initialize browser and database connection"""
        logger.info("🔐 Logging in to KenPom...")
        self.browser = login(self.email, self.password)
        logger.info("✅ Successfully authenticated to KenPom")
        
        self.conn = sqlite3.connect(self.db_path)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup"""
        if self.conn:
            self.conn.close()
    
    def scrape_efficiency_stats(self, season: int) -> pd.DataFrame:
        """Scrape efficiency and tempo stats"""
        logger.info(f"📊 Scraping efficiency stats for {season}...")
        time.sleep(self.rate_limit)
        return summary.get_efficiency(self.browser, season=str(season))
    
    def scrape_four_factors(self, season: int) -> pd.DataFrame:
        """Scrape Four Factors"""
        logger.info(f"📊 Scraping Four Factors for {season}...")
        time.sleep(self.rate_limit)
        return summary.get_fourfactors(self.browser, season=str(season))
    
    def scrape_height_experience(self, season: int) -> pd.DataFrame:
        """Scrape height and experience stats"""
        logger.info(f"📊 Scraping height/experience for {season}...")
        time.sleep(self.rate_limit)
        return summary.get_height(self.browser, season=str(season))
    
    def scrape_team_stats_offense(self, season: int) -> pd.DataFrame:
        """Scrape offensive team stats"""
        logger.info(f"📊 Scraping offensive team stats for {season}...")
        time.sleep(self.rate_limit)
        return summary.get_teamstats(self.browser, defense=False, season=str(season))
    
    def scrape_team_stats_defense(self, season: int) -> pd.DataFrame:
        """Scrape defensive team stats"""
        logger.info(f"📊 Scraping defensive team stats for {season}...")
        time.sleep(self.rate_limit)
        return summary.get_teamstats(self.browser, defense=True, season=str(season))
    
    def scrape_point_distribution(self, season: int) -> pd.DataFrame:
        """Scrape point distribution stats"""
        logger.info(f"📊 Scraping point distribution for {season}...")
        time.sleep(self.rate_limit)
        return summary.get_pointdist(self.browser, season=str(season))
    
    def update_kenpom_ratings(self, df: pd.DataFrame, season: int) -> int:
        """Update kenpom_ratings table with efficiency data"""
        if df is None or len(df) == 0:
            return 0
        
        cursor = self.conn.cursor()
        updated = 0
        
        for _, row in df.iterrows():
            try:
                team_name = row.get('Team', '')
                
                # Find team_id
                team_id = cursor.execute("""
                    SELECT team_id FROM teams 
                    WHERE team_name LIKE ? OR kenpom_name = ?
                    LIMIT 1
                """, (f"%{team_name}%", team_name)).fetchone()
                
                if not team_id:
                    continue
                
                team_id = team_id[0]
                
                # Insert/update kenpom_ratings
                cursor.execute("""
                    INSERT INTO kenpom_ratings (
                        team_id, season, rank, 
                        adj_em, adj_o, adj_o_rank, adj_d, adj_d_rank,
                        adj_tempo, adj_tempo_rank
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(team_id, season) DO UPDATE SET
                        rank = excluded.rank,
                        adj_em = excluded.adj_em,
                        adj_o = excluded.adj_o,
                        adj_o_rank = excluded.adj_o_rank,
                        adj_d = excluded.adj_d,
                        adj_d_rank = excluded.adj_d_rank,
                        adj_tempo = excluded.adj_tempo,
                        adj_tempo_rank = excluded.adj_tempo_rank
                """, (
                    team_id, season, row.get('Rank'),
                    row.get('AdjEM'), row.get('AdjO'), row.get('AdjO.1'),
                    row.get('AdjD'), row.get('AdjD.1'),
                    row.get('AdjT'), row.get('AdjT.1')
                ))
                
                updated += 1
                
            except Exception as e:
                logger.error(f"❌ Error updating {team_name}: {e}")
                continue
        
        self.conn.commit()
        return updated
    
    def update_team_advanced_stats(self, ff_df: pd.DataFrame, ts_off: pd.DataFrame, 
                                   ts_def: pd.DataFrame, season: int) -> int:
        """Update team_advanced_stats table"""
        cursor = self.conn.cursor()
        updated = 0
        
        # Merge dataframes on Team column
        if ff_df is not None and ts_off is not None and ts_def is not None:
            # Merge all three
            merged = ff_df.merge(ts_off, on='Team', suffixes=('', '_off'))
            merged = merged.merge(ts_def, on='Team', suffixes=('', '_def'))
            
            for _, row in merged.iterrows():
                try:
                    team_name = row.get('Team', '')
                    
                    team_id = cursor.execute("""
                        SELECT team_id FROM teams 
                        WHERE team_name LIKE ? OR kenpom_name = ?
                        LIMIT 1
                    """, (f"%{team_name}%", team_name)).fetchone()
                    
                    if not team_id:
                        continue
                    
                    team_id = team_id[0]
                    
                    cursor.execute("""
                        INSERT INTO team_advanced_stats (
                            team_id, season,
                            off_efg, off_to_pct, off_or_pct, off_ft_rate,
                            def_efg, def_to_pct, def_or_pct, def_ft_rate,
                            three_pt_pct, two_pt_pct, ft_pct, block_pct, steal_pct
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(team_id, season) DO UPDATE SET
                            off_efg = excluded.off_efg,
                            off_to_pct = excluded.off_to_pct,
                            off_or_pct = excluded.off_or_pct,
                            off_ft_rate = excluded.off_ft_rate,
                            def_efg = excluded.def_efg,
                            def_to_pct = excluded.def_to_pct,
                            def_or_pct = excluded.def_or_pct,
                            def_ft_rate = excluded.def_ft_rate,
                            three_pt_pct = excluded.three_pt_pct,
                            two_pt_pct = excluded.two_pt_pct,
                            ft_pct = excluded.ft_pct,
                            block_pct = excluded.block_pct,
                            steal_pct = excluded.steal_pct
                    """, (
                        team_id, season,
                        row.get('eFG%'), row.get('TO%'), row.get('OR%'), row.get('FTRate'),
                        row.get('eFG%.1'), row.get('TO%.1'), row.get('OR%.1'), row.get('FTRate.1'),
                        row.get('3P%'), row.get('2P%'), row.get('FT%'),
                        row.get('Blk%'), row.get('Stl%')
                    ))
                    
                    updated += 1
                    
                except Exception as e:
                    logger.error(f"❌ Error updating advanced stats for {team_name}: {e}")
                    continue
        
        self.conn.commit()
        return updated
    
    def run(self, seasons: List[int] = [2025]) -> Dict:
        """
        Main execution - scrape all team data for specified seasons
        
        Args:
            seasons: List of seasons to scrape
            
        Returns:
            Summary statistics
        """
        logger.info(f"🚀 Starting KenPom Team Data Scraping")
        logger.info(f"📅 Seasons: {seasons}")
        
        total_efficiency = 0
        total_advanced = 0
        
        for season in seasons:
            logger.info(f"\n{'='*70}")
            logger.info(f"📅 Season {season}")
            logger.info(f"{'='*70}")
            
            try:
                # Scrape efficiency/tempo
                eff_df = self.scrape_efficiency_stats(season)
                updated = self.update_kenpom_ratings(eff_df, season)
                total_efficiency += updated
                logger.info(f"✅ Updated {updated} teams with efficiency data")
                
                # Scrape four factors and team stats
                ff_df = self.scrape_four_factors(season)
                ts_off = self.scrape_team_stats_offense(season)
                ts_def = self.scrape_team_stats_defense(season)
                
                updated = self.update_team_advanced_stats(ff_df, ts_off, ts_def, season)
                total_advanced += updated
                logger.info(f"✅ Updated {updated} teams with advanced stats")
                
                # Height/experience (optional - may add table later)
                height_df = self.scrape_height_experience(season)
                logger.info(f"✅ Scraped height/experience for {len(height_df)} teams")
                
                # Point distribution (optional)
                pd_df = self.scrape_point_distribution(season)
                logger.info(f"✅ Scraped point distribution for {len(pd_df)} teams")
                
            except Exception as e:
                logger.error(f"❌ Error scraping season {season}: {e}")
                continue
        
        results = {
            'seasons_scraped': seasons,
            'teams_efficiency_updated': total_efficiency,
            'teams_advanced_updated': total_advanced
        }
        
        logger.info(f"\n{'='*70}")
        logger.info(f"✅ Team data scraping complete: {results}")
        logger.info(f"{'='*70}")
        
        return results


def main():
    """Entry point"""
    load_dotenv(Path(__file__).parent.parent / 'config.env')
    
    print("\n" + "="*70)
    print("🏀 COMPREHENSIVE KENPOM TEAM DATA SCRAPER")
    print("="*70)
    print("Scrapes ALL team-level statistics from KenPom")
    print("="*70)
    
    try:
        with KenPomTeamDataScraper(rate_limit_seconds=3.0) as scraper:
            results = scraper.run(seasons=[2024, 2025])
        
        print("\n" + "="*70)
        print("📊 FINAL RESULTS")
        print("="*70)
        print(f"📅 Seasons: {results['seasons_scraped']}")
        print(f"✅ Teams (Efficiency): {results['teams_efficiency_updated']:,}")
        print(f"✅ Teams (Advanced Stats): {results['teams_advanced_updated']:,}")
        print("="*70)
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()

