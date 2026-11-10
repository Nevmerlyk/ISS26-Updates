// Read-only PS1 ISO probe for alternate 8-bit per-glyph team-name banks.
// Finds sequence RUSSIA, UKRAINE, TURKEY, GREECE with a consistent UNKNOWN
// single-byte substitution alphabet in fixed-width adjacent records.
// Does not infer ROM ownership or patch any bytes.
#include <fstream>
#include <vector>
#include <string>
#include <iostream>
#include <cstdint>
#include <algorithm>
int main(int argc,char**argv){
 if(argc!=2)return 2;
 std::ifstream f(argv[1],std::ios::binary);if(!f)return 3;
 constexpr size_t LIMIT=48*1024*1024;
 std::vector<uint8_t>b(LIMIT);f.read((char*)b.data(),LIMIT);b.resize(f.gcount());
 size_t total=0;
 for(int stride:{8,10,12,16,20,24,32}){
  size_t n=0;
  for(size_t p=0;p+4*stride<b.size();++p){
   if(b[p+2]!=b[p+3])continue; // RUSSIA => equal Ss
   if(b[p]!=b[p+stride+2] || b[p+1]!=b[p+stride])continue; // R,U
   if(b[p+4]!=b[p+stride+4] || b[p+5]!=b[p+stride+3])continue; // I,A
   if(b[p+stride+1]!=b[p+2*stride+3])continue; // K
   if(b[p+1]!=b[p+2*stride+1] || b[p]!=b[p+2*stride+2])continue; // U,R
   if(b[p+stride+6]!=b[p+2*stride+4])continue; // E
   if(b[p]!=b[p+3*stride+1])continue; // R
   if(b[p+stride+6]!=b[p+3*stride+2] || b[p+stride+6]!=b[p+3*stride+3] || b[p+stride+6]!=b[p+3*stride+5])continue; // E,E,E
   // Require distinct images for distinct letters in a one-to-one font coding.
   const size_t st=static_cast<size_t>(stride);
   const size_t idxs[]={0,1,2,4,5,st+1,st+5,st+6,2*st,2*st+5,3*st,3*st+4};
   bool unique=true;
   for(size_t i=0;i<12&&unique;i++)for(size_t j=i+1;j<12;j++)if(b[p+idxs[i]]==b[p+idxs[j]]){unique=false;break;}
   if(!unique)continue;
   std::cout<<"candidate fixed stride="<<stride<<" raw_offset="<<p<<" first=";
   for(size_t i=0;i<6;i++)std::cout<<int(b[p+i])<<",";
   std::cout<<"\n";n++;total++;
  }
  std::cerr<<"stride="<<stride<<" candidates="<<n<<"\n";
 }
 std::cerr<<"total_candidates="<<total<<"\n";
}
