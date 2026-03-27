import { useState, useEffect } from 'react';
import { Star, ThumbsUp, ThumbsDown, TrendingUp, MessageSquare, Calendar } from 'lucide-react';
import { BarChart, Bar, PieChart, Pie, Cell, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

interface MessageRating {
  messageId: number;
  rating: 'positive' | 'negative';
  timestamp: string;
}

interface ConversationRating {
  rating: number;
  feedback: string;
  messageCount: number;
  timestamp: string;
  useOllama: boolean;
}

interface RatingsAnalyticsProps {
  showDetails?: boolean;
}

export function RatingsAnalytics({ showDetails = false }: RatingsAnalyticsProps) {
  const [messageRatings, setMessageRatings] = useState<MessageRating[]>([]);
  const [conversationRatings, setConversationRatings] = useState<ConversationRating[]>([]);

  useEffect(() => {
    loadRatings();
  }, []);

  const loadRatings = () => {
    const messages = JSON.parse(localStorage.getItem('messageRatings') || '[]');
    const conversations = JSON.parse(localStorage.getItem('conversationRatings') || '[]');
    setMessageRatings(messages);
    setConversationRatings(conversations);
  };

  // حساب الإحصائيات
  const stats = {
    totalConversations: conversationRatings.length,
    totalMessageRatings: messageRatings.length,
    averageRating: conversationRatings.length > 0
      ? (conversationRatings.reduce((sum, r) => sum + r.rating, 0) / conversationRatings.length).toFixed(1)
      : '0.0',
    satisfactionRate: conversationRatings.length > 0
      ? ((conversationRatings.filter(r => r.rating >= 4).length / conversationRatings.length) * 100).toFixed(1)
      : '0.0',
    positiveMessages: messageRatings.filter(r => r.rating === 'positive').length,
    negativeMessages: messageRatings.filter(r => r.rating === 'negative').length,
    positiveRate: messageRatings.length > 0
      ? ((messageRatings.filter(r => r.rating === 'positive').length / messageRatings.length) * 100).toFixed(1)
      : '0.0'
  };

  // توزيع النجوم
  const starDistribution = [
    { name: '1 نجمة', value: conversationRatings.filter(r => r.rating === 1).length, color: '#EF4444' },
    { name: '2 نجمة', value: conversationRatings.filter(r => r.rating === 2).length, color: '#F97316' },
    { name: '3 نجوم', value: conversationRatings.filter(r => r.rating === 3).length, color: '#EAB308' },
    { name: '4 نجوم', value: conversationRatings.filter(r => r.rating === 4).length, color: '#84CC16' },
    { name: '5 نجوم', value: conversationRatings.filter(r => r.rating === 5).length, color: '#22C55E' }
  ];

  // التقييمات حسب اليوم (آخر 7 أيام)
  const getLast7Days = () => {
    const days = [];
    for (let i = 6; i >= 0; i--) {
      const date = new Date();
      date.setDate(date.getDate() - i);
      const dateStr = date.toISOString().split('T')[0];
      const dayRatings = conversationRatings.filter(r => r.timestamp.startsWith(dateStr));
      const avg = dayRatings.length > 0
        ? dayRatings.reduce((sum, r) => sum + r.rating, 0) / dayRatings.length
        : 0;
      
      days.push({
        day: date.toLocaleDateString('ar-PS', { weekday: 'short' }),
        متوسط: Number(avg.toFixed(1)),
        عدد: dayRatings.length
      });
    }
    return days;
  };

  const weeklyData = getLast7Days();

  // مقارنة Ollama vs النظام الأساسي
  const ollamaRatings = conversationRatings.filter(r => r.useOllama);
  const basicRatings = conversationRatings.filter(r => !r.useOllama);
  
  const comparisonData = [
    {
      name: 'Ollama AI',
      متوسط: ollamaRatings.length > 0
        ? Number((ollamaRatings.reduce((sum, r) => sum + r.rating, 0) / ollamaRatings.length).toFixed(1))
        : 0,
      عدد: ollamaRatings.length
    },
    {
      name: 'النظام الأساسي',
      متوسط: basicRatings.length > 0
        ? Number((basicRatings.reduce((sum, r) => sum + r.rating, 0) / basicRatings.length).toFixed(1))
        : 0,
      عدد: basicRatings.length
    }
  ];

  // آخر الملاحظات
  const recentFeedback = conversationRatings
    .filter(r => r.feedback && r.feedback.trim())
    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
    .slice(0, 5);

  return (
    <div className="space-y-6" dir="rtl">
      {/* بطاقات الإحصائيات */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-gradient-to-br from-blue-500 to-blue-600 text-white rounded-xl shadow-lg p-6">
          <div className="flex items-center justify-between mb-2">
            <Star className="w-8 h-8" />
            <span className="text-3xl font-bold">{stats.averageRating}</span>
          </div>
          <h3 className="text-blue-100 text-sm">متوسط التقييم</h3>
          <p className="text-xs text-blue-200 mt-1">من {stats.totalConversations} تقييم</p>
        </div>

        <div className="bg-gradient-to-br from-green-500 to-green-600 text-white rounded-xl shadow-lg p-6">
          <div className="flex items-center justify-between mb-2">
            <TrendingUp className="w-8 h-8" />
            <span className="text-3xl font-bold">{stats.satisfactionRate}%</span>
          </div>
          <h3 className="text-green-100 text-sm">نسبة الرضا</h3>
          <p className="text-xs text-green-200 mt-1">تقييم 4-5 نجوم</p>
        </div>

        <div className="bg-gradient-to-br from-purple-500 to-purple-600 text-white rounded-xl shadow-lg p-6">
          <div className="flex items-center justify-between mb-2">
            <ThumbsUp className="w-8 h-8" />
            <span className="text-3xl font-bold">{stats.positiveRate}%</span>
          </div>
          <h3 className="text-purple-100 text-sm">تقييمات إيجابية</h3>
          <p className="text-xs text-purple-200 mt-1">{stats.positiveMessages} من {stats.totalMessageRatings}</p>
        </div>

        <div className="bg-gradient-to-br from-orange-500 to-orange-600 text-white rounded-xl shadow-lg p-6">
          <div className="flex items-center justify-between mb-2">
            <MessageSquare className="w-8 h-8" />
            <span className="text-3xl font-bold">{stats.totalConversations}</span>
          </div>
          <h3 className="text-orange-100 text-sm">إجمالي المحادثات</h3>
          <p className="text-xs text-orange-200 mt-1">{stats.totalMessageRatings} تقييم رسالة</p>
        </div>
      </div>

      {/* الرسوم البيانية */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* توزيع النجوم */}
        <div className="bg-white rounded-xl shadow-md p-6">
          <h3 className="text-xl font-bold text-gray-800 mb-4">توزيع التقييمات</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={starDistribution}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={(entry) => entry.value > 0 ? `${entry.name}: ${entry.value}` : ''}
                outerRadius={100}
                fill="#8884d8"
                dataKey="value"
              >
                {starDistribution.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* التقييمات الأسبوعية */}
        <div className="bg-white rounded-xl shadow-md p-6">
          <h3 className="text-xl font-bold text-gray-800 mb-4">التقييمات الأسبوعية</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={weeklyData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="day" />
              <YAxis domain={[0, 5]} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="متوسط" stroke="#3B82F6" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* مقارنة Ollama vs النظام الأساسي */}
        {(ollamaRatings.length > 0 || basicRatings.length > 0) && (
          <div className="bg-white rounded-xl shadow-md p-6">
            <h3 className="text-xl font-bold text-gray-800 mb-4">مقارنة الأداء</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={comparisonData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis domain={[0, 5]} />
                <Tooltip />
                <Legend />
                <Bar dataKey="متوسط" fill="#8B5CF6" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* تقييمات الرسائل */}
        <div className="bg-white rounded-xl shadow-md p-6">
          <h3 className="text-xl font-bold text-gray-800 mb-4">تقييمات الرسائل</h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-green-50 rounded-lg">
              <div className="flex items-center gap-3">
                <ThumbsUp className="w-6 h-6 text-green-600" />
                <span className="font-semibold text-gray-800">إيجابي</span>
              </div>
              <span className="text-2xl font-bold text-green-600">{stats.positiveMessages}</span>
            </div>
            <div className="flex items-center justify-between p-4 bg-red-50 rounded-lg">
              <div className="flex items-center gap-3">
                <ThumbsDown className="w-6 h-6 text-red-600" />
                <span className="font-semibold text-gray-800">سلبي</span>
              </div>
              <span className="text-2xl font-bold text-red-600">{stats.negativeMessages}</span>
            </div>
            <div className="p-4 bg-blue-50 rounded-lg">
              <div className="flex justify-between mb-2">
                <span className="text-sm text-gray-600">نسبة الإيجابية</span>
                <span className="text-sm font-semibold text-blue-600">{stats.positiveRate}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-3">
                <div
                  className="bg-blue-500 h-3 rounded-full transition-all"
                  style={{ width: `${stats.positiveRate}%` }}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* آخر الملاحظات */}
      {showDetails && recentFeedback.length > 0 && (
        <div className="bg-white rounded-xl shadow-md p-6">
          <h3 className="text-xl font-bold text-gray-800 mb-4">آخر الملاحظات والتعليقات</h3>
          <div className="space-y-4">
            {recentFeedback.map((rating, idx) => (
              <div key={idx} className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    {[...Array(5)].map((_, i) => (
                      <Star
                        key={i}
                        className={`w-4 h-4 ${
                          i < rating.rating ? 'fill-yellow-400 text-yellow-400' : 'text-gray-300'
                        }`}
                      />
                    ))}
                    <span className="text-sm font-semibold text-gray-700">
                      {rating.rating}/5
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-gray-500">
                    <Calendar className="w-4 h-4" />
                    <span>{new Date(rating.timestamp).toLocaleDateString('ar-PS')}</span>
                  </div>
                </div>
                <p className="text-gray-700 leading-relaxed">{rating.feedback}</p>
                <div className="mt-2 flex items-center gap-2">
                  <span className={`text-xs px-2 py-1 rounded-full ${
                    rating.useOllama
                      ? 'bg-purple-100 text-purple-700'
                      : 'bg-blue-100 text-blue-700'
                  }`}>
                    {rating.useOllama ? '🤖 Ollama AI' : '📚 النظام الأساسي'}
                  </span>
                  <span className="text-xs text-gray-500">
                    {rating.messageCount} رسالة
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* رسالة في حالة عدم وجود بيانات */}
      {conversationRatings.length === 0 && messageRatings.length === 0 && (
        <div className="bg-white rounded-xl shadow-md p-12 text-center">
          <MessageSquare className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-xl font-bold text-gray-800 mb-2">لا توجد تقييمات بعد</h3>
          <p className="text-gray-600">سيتم عرض التقييمات والإحصائيات هنا بمجرد بدء المستخدمين بتقييم الخدمة</p>
        </div>
      )}
    </div>
  );
}
