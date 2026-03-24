import { Users, UserCheck } from 'lucide-react';
import { motion } from "framer-motion";


interface RoleSelectionProps {
  onSelectRole: (role: 'citizen' | 'employee' | 'admin') => void;
}

export function RoleSelection({ onSelectRole }: RoleSelectionProps) {
  const roles = [
    {
      id: 'citizen',
      title: 'مواطن',
      description: 'الدخول إلى نظام الدعم الذكي والاستفسارات',
      icon: Users,
      color: 'from-blue-500 to-blue-600',
      hoverColor: 'hover:from-blue-600 hover:to-blue-700'
    },
    {
      id: 'employee',
      title: 'موظف / مدير',
      description: 'إدارة الردود ومراقبة الأداء والإعدادات',
      icon: UserCheck,
      color: 'from-green-500 to-green-600',
      hoverColor: 'hover:from-green-600 hover:to-green-700'
    }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-green-50 to-purple-50 flex flex-col items-center justify-center p-4" dir="rtl">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="text-center mb-12"
      >
        <div className="w-24 h-24 bg-gradient-to-br from-blue-600 to-green-600 rounded-3xl mx-auto mb-6 flex items-center justify-center shadow-2xl">
          <svg className="w-12 h-12 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>
        <h1 className="text-5xl font-bold text-gray-800 mb-4">
          نظام الدعم الذكي
        </h1>
        <p className="text-xl text-gray-600">
          كهرباء الخليل
        </p>
        <p className="text-gray-500 mt-2">
          مدعوم بالذكاء الاصطناعي ومعالجة اللغة الطبيعية
        </p>
      </motion.div>

      {/* Role Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl w-full">
        {roles.map((role, index) => (
          <motion.button
            key={role.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: index * 0.1 }}
            whileHover={{ scale: 1.05, y: -5 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => onSelectRole(role.id as 'citizen' | 'employee' | 'admin')}
            className={`bg-gradient-to-br ${role.color} ${role.hoverColor} text-white rounded-2xl shadow-2xl p-8 transition-all duration-300`}
          >
            <div className="flex flex-col items-center text-center">
              <div className="w-20 h-20 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center mb-6">
                <role.icon className="w-10 h-10" />
              </div>
              <h2 className="text-3xl font-bold mb-3">{role.title}</h2>
              <p className="text-white/90 text-lg leading-relaxed">
                {role.description}
              </p>
              <div className="mt-6 w-full h-1 bg-white/30 rounded-full">
                <div className="h-full bg-white rounded-full w-0 group-hover:w-full transition-all duration-500" />
              </div>
            </div>
          </motion.button>
        ))}
      </div>

      {/* Features */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.8, delay: 0.5 }}
        className="mt-16 grid grid-cols-1 md:grid-cols-4 gap-6 max-w-6xl w-full"
      >
        {[
          { icon: '⚡', text: 'استجابة فورية' },
          { icon: '🤖', text: 'ذكاء اصطناعي متقدم' },
          { icon: '📊', text: 'تقارير شاملة' },
          { icon: '🔒', text: 'أمان عالي' }
        ].map((feature, idx) => (
          <div key={idx} className="bg-white/80 backdrop-blur-sm rounded-xl p-4 text-center shadow-lg">
            <div className="text-4xl mb-2">{feature.icon}</div>
            <p className="text-gray-700 font-semibold">{feature.text}</p>
          </div>
        ))}
      </motion.div>

      {/* Footer */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 1, delay: 0.8 }}
        className="mt-12 text-center text-gray-500 text-sm"
      >
        <p>© 2026 كهرباء الخليل - جميع الحقوق محفوظة</p>
        <p className="mt-1">نسخة تجريبية v1.0.0</p>
      </motion.div>
    </div>
  );
}
