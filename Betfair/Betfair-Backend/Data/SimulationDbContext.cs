using Microsoft.EntityFrameworkCore;
using Betfair.Models.Simulation;

namespace Betfair.Data
{
    /// <summary>
    /// Database context for betting simulation data
    /// </summary>
    public class SimulationDbContext : DbContext
    {
        public SimulationDbContext(DbContextOptions<SimulationDbContext> options) : base(options)
        {
        }

        public DbSet<SimulatedBet> SimulatedBets { get; set; }

        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {
            base.OnModelCreating(modelBuilder);

            // Configure SimulatedBet entity
            modelBuilder.Entity<SimulatedBet>(entity =>
            {
                entity.HasKey(e => e.Id);
                
                entity.Property(e => e.MarketId)
                    .IsRequired()
                    .HasMaxLength(50);
                
                entity.Property(e => e.HorseName)
                    .IsRequired()
                    .HasMaxLength(100);
                
                entity.Property(e => e.BetType)
                    .IsRequired()
                    .HasMaxLength(20)
                    .HasDefaultValue("PLACE");
                
                entity.Property(e => e.Stake)
                    .HasColumnType("decimal(10,2)")
                    .IsRequired();
                
                entity.Property(e => e.Odds)
                    .HasColumnType("decimal(8,2)")
                    .IsRequired();
                
                entity.Property(e => e.MLConfidence)
                    .HasColumnType("decimal(5,4)")
                    .IsRequired();
                
                entity.Property(e => e.MarketPosition)
                    .HasMaxLength(20);
                
                entity.Property(e => e.EventName)
                    .HasMaxLength(200);
                
                entity.Property(e => e.MarketName)
                    .HasMaxLength(200);
                
                entity.Property(e => e.ProfitLoss)
                    .HasColumnType("decimal(10,2)");
                
                entity.Property(e => e.Notes)
                    .HasMaxLength(500);
                
                // Indexes for performance
                entity.HasIndex(e => e.MarketId);
                entity.HasIndex(e => e.SelectionId);
                entity.HasIndex(e => e.PlacedAt);
                entity.HasIndex(e => e.EventTime);
                entity.HasIndex(e => e.Status);
                entity.HasIndex(e => new { e.MarketId, e.SelectionId });
            });
        }
    }
}
