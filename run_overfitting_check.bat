@echo off
echo.
echo 🔍 Running Overfitting Detection Tests...
echo.
echo This will run 3 comprehensive tests:
echo   1. Walk-Forward Analysis (IS vs OOS performance)
echo   2. Parameter Robustness (sensitivity to parameter changes)
echo   3. Period Stability (consistency across years)
echo.
echo ⏳ This may take 5-10 minutes...
echo.
python scripts\validate_overfitting.py
echo.
echo ✅ Tests completed! Check the CSV files for detailed results.
echo.
pause
