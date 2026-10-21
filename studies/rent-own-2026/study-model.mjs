export function payment(principal, rate, years) {
  if (![principal,rate,years].every(Number.isFinite) || principal<0 || rate<0 || years<=0 || !Number.isInteger(years*12)) throw Error('Invalid loan input');
  if (!principal) return 0;
  const n=years*12,r=rate/12;
  const result=r ? principal*r / -Math.expm1(-n*Math.log1p(r)) : principal/n;
  if (!Number.isFinite(result)) throw Error('Loan calculation exceeds numeric range; revise inputs');
  return result;
}
export function evaluate(price,gross,s) {
  const keys=['down_payment_fraction','annual_interest_rate','loan_years','occupied_months','management_fraction','property_tax_fraction','insurance_fraction','maintenance_reserve_fraction','monthly_utilities','monthly_hoa','annual_other_costs','annual_mortgage_insurance'];
  if (![price,gross,...keys.map(k=>s[k])].every(Number.isFinite) || price<=0 || gross<0 || keys.some(k=>s[k]<0) || s.down_payment_fraction>1 || s.management_fraction>=1 || s.occupied_months>12) throw Error('Enter valid, finite inputs; management must be below 100%.');
  if (gross<s.monthly_utilities) throw Error('Utility deduction exceeds this HUD rent.');
  const receipts=(gross-s.monthly_utilities)*s.occupied_months,management=receipts*s.management_fraction;
  const tax=price*s.property_tax_fraction,insurance=price*s.insurance_fraction,reserve=price*s.maintenance_reserve_fraction;
  const fixed=tax+insurance+reserve+12*s.monthly_hoa+s.annual_other_costs+s.annual_mortgage_insurance;
  const debt=12*payment(price*(1-s.down_payment_fraction),s.annual_interest_rate,s.loan_years);
  const denom=s.occupied_months*(1-s.management_fraction);
  if (!denom && s.occupied_months!==0) throw Error('Cash-budget calculation exceeds numeric range; revise inputs');
  const result={annual_receipts:receipts,annual_management:management,annual_property_tax:tax,annual_insurance:insurance,annual_maintenance_reserve:reserve,annual_fixed_budget:fixed,annual_principal_interest:debt,annual_cash_surplus:receipts-management-fixed-debt,break_even_gross_monthly_rent:denom?s.monthly_utilities+(fixed+debt)/denom:null,input_status:'illustrative'};
  if (Object.entries(result).some(([key,value])=>key!=='input_status' && value!==null && !Number.isFinite(value))) throw Error('Cash-budget calculation exceeds numeric range; revise inputs');
  return result;
}
export function summarize(m,s) {
  const details=m.areas.map(a=>({...a,result:evaluate(m.price,a.rent,s)}));
  const values=details.map(a=>a.result.annual_cash_surplus);
  const endpoints=m.areas.flatMap(a=>[evaluate(m.price-m.moe,a.rent,s).annual_cash_surplus,evaluate(m.price+m.moe,a.rent,s).annual_cash_surplus]);
  return {details,min:Math.min(...values),max:Math.max(...values),priceMin:Math.min(...endpoints),priceMax:Math.max(...endpoints),threshold:details[0].result.break_even_gross_monthly_rent};
}
