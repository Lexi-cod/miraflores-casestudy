"""Read-only arithmetic explanations using this packet's stated rules and inputs.

These checks never replace engine results or propagate working adjustments.
"""
import math
import re


def explain_all(app, state):
    lines = app.lines(state)
    parameters = app.PACKET['engine_reference']['parameters']
    extracted = {e['id']: e for e in app.PACKET['extracted_values']}
    subtraction = {'SchC.29','SchC.31','SchE.21A','SchE.21B','F1040.11','F1040.15','F1040.22','F1040.37',
                   'F6251.6','F6251.9','F6251.10','F6251.11','F8812.12','F540NR.17','F540NR.19','F540NR.32','F540NR.40',
                   'F8606.14','F8606.18','F4797.24','F4797.25','F4797.9','F7203.7'}
    nonnegative = {'F1040.15','F1040.22','F1040.37','F6251.6','F6251.11','F8812.12','F540NR.19','F540NR.40','F8606.14','F8606.18','F7203.7'}

    def explain(line, working):
        key, rule = line['key'], line['rule']
        refs, steps = [], []
        def value(ref):
            if ref not in refs: refs.append(ref)
            if ref in lines: result = app.effective(state,ref) if working else lines[ref]['value']
            elif ref.startswith('ref:param.'): result = parameters[ref[10:]]
            else:
                result = extracted.get(ref) or app.resolve(ref,state)
                if isinstance(result,dict): result = result.get('value')
            if type(result) not in [int,float]: raise ValueError('A numeric input is not supplied')
            return result
        def param(name):return value('ref:param.'+name)
        def step(label, amount, unit='money'):
            steps.append(dict(label=label,value=amount,unit=unit));return amount
        def inputs():return [value(r) for r in line['inputs']]
        result = None
        unit = 'ratio' if rule=='R-CA-RATIO' or 'ratio' in line['label'].lower() or 'percentage' in line['label'].lower() or key=='F8606.10' else 'money'
        # Column D also includes the separately supplied California additions/subtractions.
        if re.fullmatch(r'SchCA540NR\.\d+\.D',key) and key not in ['SchCA540NR.22.D','SchCA540NR.26.D']:
            base=key[:-1]
            federal=step('Federal amount',value(base+'A'))
            subtract=step('California subtractions',value(base+'B') if base+'B' in lines else 0)
            add=step('California additions',value(base+'C') if base+'C' in lines else 0)
            result=step('Federal − subtractions + additions',federal-subtract+add)
        elif key=='F540NR.64':result=step('Regular tax − other-state credit + California AMT',value('F540NR.40')-value('ScheduleS.credit')+value('F540NR.61'))
        elif key=='F540NR.97':result=step('Payments − total tax, not below zero',max(0,value('F540NR.78')-value('F540NR.64')))
        elif key in subtraction:
            amounts=inputs();result=amounts[0]-sum(amounts[1:])
            if key in nonnegative:result=max(0,result)
            step('First input − remaining inputs'+(' · minimum zero' if key in nonnegative else ''),result)
        elif rule=='R-SUM' and line['inputs']:result=step('Sum of listed inputs',sum(inputs()))
        elif rule=='R-CARRY' and len(line['inputs'])==1:result=step('Carried from source line',inputs()[0])
        elif rule=='R-DEDUCTION-CHOICE':result=step('Larger of itemized or standard deduction',max(value('SchA.17'),param('std_deduction_mfj')))
        elif rule=='R-CA-DEDUCTION':result=step('Larger of CA itemized or standard deduction',max(value('SchCA540NR.A.itemized'),param('ca_std_deduction_mfj')))
        elif rule=='R-SALT-CAP':
            excess=step('AGI above phase-down threshold',max(0,value('F1040.11')-param('salt_cap_phase_start')))
            cap=step('Reduced cap, subject to floor',max(param('salt_cap_floor'),param('salt_cap')-excess*param('salt_cap_phase_rate')))
            result=step('Smaller of taxes paid and applicable cap',min(value('SchA.5d'),cap))
        elif key=='SchSE.4a':result=step('Net profit × supplied SE factor',value('SchSE.2')*param('se_factor'))
        elif key=='SchSE.13':result=step('One-half of self-employment tax',value('SchSE.12')/2)
        elif rule=='R-STANDARD-MILEAGE':result=step('Business miles × supplied mileage rate',inputs()[0]*param('mileage_rate'))
        elif key=='F8606.10':result=step('Basis ÷ total distributions and year-end value · capped at 1',min(1,value('F8606.5')/value('F8606.9')),'ratio')
        elif key=='F8606.11':result=step('Amount converted × nontaxable fraction',value('F8606.8')*value('F8606.10'))
        elif key=='F7203.excess':result=step('Distributions − basis before distributions · minimum zero',max(0,value('F7203.6')-value('F7203.5')))
        elif key=='SchD.19':result=step('Smaller of depreciation allowed and sale gain',min(value('F4797.23'),value('F4797.25')))
        elif key=='F8812.5':result=step('Qualifying children × supplied credit',value('F8812.4')*param('ctc_per_child'))
        elif key=='F8812.7':result=step('Other dependents × supplied credit',value('F8812.6')*param('odc_per_dependent'))
        elif key=='F8812.11':
            excess=step('Modified AGI above phase-out threshold',max(0,value('F8812.1')-param('ctc_phaseout_start')))
            blocks=step('Thousands, rounded up',math.ceil(excess/1000),'number')
            result=step('$50 per thousand under the supplied rule',blocks*50)
        elif key=='F8863.7':
            low,high=parameters['aotc_phaseout'];refs.append('ref:param.aotc_phaseout')
            fraction=step('Remaining phase-out fraction',max(0,min(1,(high-value('F1040.11'))/(high-low))),'ratio')
            result=step('Tentative credit × remaining fraction',value('F8863.30')*fraction)
        elif key=='F6251.5' and value('F6251.4')<=param('amt_phaseout_start'):result=step('AMTI below phase-out start: full supplied exemption',param('amt_exemption'))
        elif key=='F8995.2.1':
            a=inputs();result=step('Business profit − half SE tax − SEP − health insurance',a[0]-sum(a[1:]))
        elif key=='F8995.33':result=step('AGI − deduction before QBI',value('F1040.11')-value('F1040.12'))
        elif key=='F8995.34':result=step('Qualified dividends + positive net long-term gain limited to overall net gain',value('F1040.3a')+max(0,min(value('SchD.15'),value('SchD.16'))))
        elif key=='F8995.39':result=step('Smaller of QBI component and income limitation',min(value('F8995.27'),value('F8995.36')))
        elif rule in ['R-CA-INTEREST-SOURCE','R-CA-DIVIDENDS-SOURCE','R-CA-BUSINESS-SOURCE','R-CA-ADJ-SOURCE']:
            fraction=step('Resident days ÷ days in year',param('ca_resident_days')/param('year_days'),'ratio')
            result=step('Total amount × resident-period fraction',inputs()[0]*fraction)
        elif rule=='R-CA-RATIO':
            a=inputs();result=step('Numerator ÷ denominator',a[0]/a[1],'ratio')
        elif key=='F540NR.35':
            deduction=step('Deductions × supplied deduction percentage',value('F540NR.18')*value('F540NR.34'))
            result=step('California AGI − allocated deductions',value('F540NR.32')-deduction)
        elif key=='F540NR.37':result=step('California taxable income × supplied tax rate',value('F540NR.35')*value('F540NR.36'))
        elif rule=='R-CA-TAX-RATE-SCHEDULE':
            income=inputs()[0];lower=0;result=0;refs.append('ref:param.ca_brackets_mfj')
            for upper,rate in parameters['ca_brackets_mfj']:
                taxable=max(0,min(income,upper if upper is not None else income)-lower)
                if taxable:result+=step(f'{taxable:,.2f} in band above {lower:,.0f} × {rate:.1%}',taxable*rate)
                if upper is None or income<=upper:break
                lower=upper
        elif rule=='R-CA-ITEMIZED':result=step('Interest + charitable gifts + property tax',sum(inputs()))
        elif rule in ['R-DEPRECIATION-SCHEDULE','R-CA-DEPRECIATION'] and any(r.startswith('asset:') for r in line['sources']):
            jurisdiction='california' if line['jurisdiction']=='california' else 'federal';result=0
            for ref in line['sources']:
                if ref.startswith('asset:'):
                    asset=app.resolve(ref,state);refs.append(ref)
                    result+=step(asset['description']+' · '+jurisdiction,asset[jurisdiction]['depreciation_2025'])
        if result is None:return None
        rounded=round(result,5 if key=='F8606.10' else 4) if unit=='ratio' else app.whole(result)
        target=app.effective(state,key) if working else line['value']
        return dict(steps=steps,refs=refs,result=result,rounded=rounded,unit=unit,difference=rounded-target,
                    note='Arithmetic check using linked '+('working' if working else 'engine')+' inputs. Supplied inputs may already be rounded. Differences require review; no return amount is changed.')

    results={}
    for key,line in lines.items():
        if type(line['value']) not in [int,float]:continue
        try:
            engine=explain(line,False)
            if engine:
                results[key]=dict(engine=engine,working=explain(line,True))
        except (ValueError,KeyError,StopIteration,ZeroDivisionError,TypeError,IndexError):
            # An incomplete packet/import retains the explicit source/rule view.
            continue
    return results
