@echo off
echo.
echo ========================================
echo ADVANCED OVERFITTING VALIDATION SUITE
echo ========================================
echo.
echo This comprehensive test suite includes:
echo   1. Anchored Walk-Forward (expanding window)
echo   2. Rolling Walk-Forward (3Y train / 6M test)
echo   3. Random Seed Stress Test (20 iterations)
echo   4. Regime-Based Performance Analysis
echo.
echo Expected runtime: 10-15 minutes
echo.
pause
echo.
echo Running validation tests...
echo.
python scripts\advanced_overfitting_validation.py
echo.
echo ========================================
echo VALIDATION COMPLETE
echo ========================================
echo.
echo Results saved to:
echo   - anchored_walk_forward.csv
echo   - rolling_walk_forward.csv
echo   - random_seed_stress_test.csv
echo.
pause
