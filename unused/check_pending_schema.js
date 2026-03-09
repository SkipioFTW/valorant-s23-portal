const { createClient } = require('@supabase/supabase-js');
require('dotenv').config({ path: 'new_app_repo/.env' });

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!supabaseUrl || !supabaseKey) {
    console.error('Missing Supabase credentials');
    process.exit(1);
}

const supabase = createClient(supabaseUrl, supabaseKey);

async function checkSchema() {
    const { data, error } = await supabase.rpc('get_table_schema', { table_name: 'pending_matches' });
    if (error) {
        // Fallback: try to select one row
        const { data: row, error: rowErr } = await supabase.from('pending_matches').select('*').limit(1);
        if (rowErr) {
            console.error('Error fetching row:', rowErr);
        } else {
            console.log('Sample row columns:', Object.keys(row[0] || {}));
        }
    } else {
        console.log('Schema:', data);
    }
}

checkSchema();
