# 🔑 Getting Perplexity API Key - Complete Guide

## 🌟 Why Choose Perplexity for Signal Validation?

### **Unique Advantages:**
✅ **Real-time Market Data** - Access to current market conditions and news  
✅ **Web Search Integration** - Pulls live information from financial websites  
✅ **Cost Effective** - Generally 30-50% cheaper than OpenAI/Anthropic  
✅ **Source Citations** - Provides references for analysis claims  
✅ **Current Market Context** - Incorporates breaking news and market sentiment  

## 🚀 How to Get Perplexity API Key

### **Step 1: Sign Up for Perplexity**
1. Go to: https://www.perplexity.ai/
2. Click **"Sign Up"** or **"Get Started"**
3. Create account with email/Google/Discord
4. Verify your email address

### **Step 2: Access API Portal**
1. Once logged in, look for:
   - **"API"** in the menu
   - **"Developers"** section
   - **"Settings"** → **"API"**
2. Or directly visit: https://www.perplexity.ai/settings/api

### **Step 3: Request API Access**
Perplexity API access may require:
- **Waitlist Registration** (if in beta)
- **Application Process** (provide use case details)
- **Account Verification** (may require phone verification)

### **Step 4: Generate API Key**
Once approved:
1. Go to API dashboard
2. Click **"Create New API Key"**
3. Name your key (e.g., "Trading System")
4. **Copy and save the key immediately** (won't be shown again)

## 💳 Pricing Information

### **Current Pricing (as of Oct 2025):**
- **Sonar Small**: ~$0.20 per 1M tokens
- **Sonar Large**: ~$1.00 per 1M tokens  
- **Web Search**: Additional ~$5 per 1K requests

### **Estimated Costs for Trading:**
- **Per Signal Validation**: $0.01-0.02
- **50 signals/day**: ~$0.75/day ($22.50/month)
- **100 signals/day**: ~$1.50/day ($45/month)

## ⚙️ Integration Setup

### **1. Add to Your `.env` File:**
```bash
# Enable Perplexity validation
LLM_VALIDATION_ENABLED=true
LLM_PRIMARY_PROVIDER=perplexity
PERPLEXITY_API_KEY=your_perplexity_api_key_here

# Optional: Adjust settings for Perplexity
LLM_VALIDATION_TIMEOUT=15  # Perplexity may need more time for web search
LLM_MIN_CONFIDENCE=0.75
```

### **2. Restart Your Trading System:**
```bash
python production_server.py
```

### **3. Test the Integration:**
1. Generate some trading signals
2. Go to Signals page
3. Click AI robot icon (🤖) next to any signal
4. Verify you see real-time market analysis

## 🎯 Perplexity-Specific Features

### **Real-time Market Analysis**
```json
{
  "validation_result": "approve",
  "confidence": 0.82,
  "reasoning": "Based on current market data from Yahoo Finance and MarketWatch, RELIANCE shows strong bullish momentum with positive earnings sentiment...",
  "market_sources": [
    "finance.yahoo.com",
    "marketwatch.com", 
    "bloomberg.com"
  ],
  "real_time_context": {
    "market_sentiment": "bullish",
    "recent_news": "Positive Q3 earnings beat expectations",
    "sector_performance": "Energy sector outperforming"
  }
}
```

### **Source Citations**
Perplexity provides citations for its analysis:
- Yahoo Finance data
- MarketWatch news
- Bloomberg reports
- Economic indicators

## 🔧 Configuration Options

### **Model Selection**
- **llama-3.1-sonar-small-128k-online** (Default) - Faster, cheaper
- **llama-3.1-sonar-large-128k-online** - More detailed analysis

### **Search Domain Filtering**
The system is configured to search only reliable financial sources:
```python
"search_domain_filter": [
    "finance.yahoo.com",
    "marketwatch.com", 
    "bloomberg.com",
    "moneycontrol.com"
]
```

### **Real-time Features**
- **return_citations**: Get source references
- **search_recency_filter**: Focus on recent news
- **temperature**: 0.1 for consistent analysis

## 🚨 Common Issues & Solutions

### **"API Key Invalid"**
- Verify you copied the complete key
- Check for extra spaces or characters
- Ensure your account has API access approved

### **"Rate Limited"**
- Perplexity has rate limits (usually 20-100 requests/minute)
- Consider adding delays between validations
- Upgrade to higher tier if needed

### **"Timeout Errors"**
- Web search takes longer than standard LLM calls
- Increase `LLM_VALIDATION_TIMEOUT` to 15-20 seconds
- Check your internet connection

### **"Insufficient Credits"**
- Add payment method to your Perplexity account
- Monitor usage in the dashboard
- Set up billing alerts

## 🔒 Security Best Practices

### **API Key Protection**
- Store in `.env` file only
- Never commit to version control
- Use separate keys for dev/production
- Rotate keys regularly

### **Usage Monitoring**
- Set daily/monthly usage limits
- Monitor costs in Perplexity dashboard
- Set up billing alerts
- Track validation accuracy vs cost

## 📊 Performance Comparison

### **Perplexity vs Other Providers**

| Aspect | Perplexity | OpenAI GPT-4 | Anthropic Claude |
|--------|------------|--------------|------------------|
| **Real-time Data** | ✅ Excellent | ❌ Limited | ❌ Limited |
| **Market Context** | ✅ Current | ⚠️ Training data | ⚠️ Training data |
| **Cost** | ✅ Low | ❌ High | ⚠️ Medium |
| **Speed** | ⚠️ Slower (web search) | ✅ Fast | ✅ Fast |
| **Accuracy** | ✅ Good with sources | ✅ Excellent | ✅ Excellent |
| **Citations** | ✅ Yes | ❌ No | ❌ No |

## 🎯 Best Use Cases for Perplexity

### **Ideal Scenarios:**
1. **News-sensitive Trading** - Stocks affected by current events
2. **Earnings Season** - Real-time earnings analysis
3. **Market Volatility** - Current market sentiment analysis
4. **Sector Rotation** - Live sector performance data
5. **Economic Events** - Fed meetings, policy changes, etc.

### **When to Use Others:**
- **Complex Technical Analysis** → OpenAI GPT-4
- **Conservative Risk Assessment** → Anthropic Claude
- **Cost-sensitive High Volume** → Perplexity
- **Real-time Market Updates** → Perplexity

## 📈 Success Metrics

Track these to evaluate Perplexity's effectiveness:

### **Validation Quality:**
- **Source Reliability** - Quality of cited sources
- **Timeliness** - How current is the market data
- **Accuracy** - Validation vs actual signal performance

### **Cost Effectiveness:**
- **Cost per Validation** - Monitor actual spend
- **ROI Impact** - Performance improvement vs cost
- **Usage Efficiency** - Optimal validation frequency

## 🤝 Support & Resources

### **Getting Help:**
1. **Perplexity Support**: support@perplexity.ai
2. **API Documentation**: https://docs.perplexity.ai/
3. **Community Discord**: Available through their website
4. **Status Page**: Check for API outages

### **Useful Links:**
- **API Dashboard**: https://www.perplexity.ai/settings/api
- **Pricing Page**: https://www.perplexity.ai/pricing
- **Documentation**: https://docs.perplexity.ai/
- **Usage Analytics**: Available in dashboard

---

## 🚀 Quick Start Checklist

- [ ] Sign up for Perplexity account
- [ ] Request API access (may take 1-3 days)
- [ ] Generate API key
- [ ] Add `PERPLEXITY_API_KEY` to `.env` file
- [ ] Set `LLM_PRIMARY_PROVIDER=perplexity`
- [ ] Restart trading system
- [ ] Test with a sample signal validation
- [ ] Monitor costs and performance
- [ ] Adjust settings based on results

**Ready to get started with real-time market analysis?** 🎯

Your signals will now have access to current market conditions, breaking news, and live financial data to make more informed trading decisions!